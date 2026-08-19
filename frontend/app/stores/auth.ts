import { defineStore } from 'pinia'
import type { AuthResponse, AuthUser, LoginResponse, MfaChallenge, MfaChallengeDetailsResponse, MfaMethod, MfaSecurityStatus, OAuthAccount, OAuthProvider, Passkey, TotpSetup, VerificationResponse, WebAuthnOptionsResponse } from '~/types/auth'
import { buildApiUrl } from '~/utils/apiUrl'
import { sanitizeInternalRedirect } from '~/utils/redirect'
import { authenticateWithPasskey, createPasskey } from '~/utils/webauthn'
import { normalizeRecoveryCode } from '~/utils/mfa'

const initializationPromises = new WeakMap<object, Promise<void>>()

type SignupPayload = {
  email: string
  password: string
  first_name: string
  last_name: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    csrfToken: null as string | null,
    loading: false,
    initialized: false,
    refreshing: false,
    sessionExpired: false,
    sessionUncertain: false,
    blockedAuthCode: '' as string,
    authGeneration: 0,
    oauthProviders: [] as OAuthProvider[],
    oauthProvidersLoading: false,
    oauthProvidersLoaded: false,
    oauthError: '' as string,
    oauthAccounts: [] as OAuthAccount[],
    mfaChallenge: null as MfaChallenge | null,
    passkeys: [] as Passkey[]
  }),
  getters: {
    authenticated: (state) => !!state.user,
    canWrite: (state) => !!state.user?.is_verified,
    displayName: (state) => state.user?.display_name || [state.user?.first_name, state.user?.last_name].filter(Boolean).join(' ') || state.user?.email || ''
  },
  actions: {
    async initialize() {
      if (this.initialized) return
      const pending = initializationPromises.get(this)
      if (pending) return await pending
      const initialization = (async () => {
        this.loading = true
        try {
          await this.refreshUser()
        } finally {
          this.loading = false
          this.initialized = true
        }
      })()
      initializationPromises.set(this, initialization)
      try { await initialization } finally { initializationPromises.delete(this) }
    },
    async loadProviders() {
      if (this.oauthProvidersLoaded || this.oauthProvidersLoading) return
      this.oauthProvidersLoading = true
      this.oauthError = ''
      try {
        const { request } = useApi()
        this.oauthProviders = await request<OAuthProvider[]>('/auth/oauth/providers', { retryOnUnauthorized: false })
        this.oauthProvidersLoaded = true
      } catch {
        this.oauthProviders = []
        this.oauthError = 'OAuth-Anbieter konnten nicht geladen werden.'
        if (import.meta.dev) {
          console.warn('Failed to load OAuth providers')
        }
      } finally {
        this.oauthProvidersLoading = false
      }
    },
    async startOAuthLogin(providerId: string, redirect?: string, instance?: string) {
      if (typeof window === 'undefined') return
      if (providerId === 'mastodon') {
        const { request } = useApi()
        const result = await request<{ authorization_url: string }>('/auth/oauth/mastodon/start', {
          method: 'POST',
          body: JSON.stringify({ instance, redirect: sanitizeInternalRedirect(redirect) }),
          retryOnUnauthorized: false
        })
        window.location.assign(result.authorization_url)
        return
      }
      const config = useRuntimeConfig()
      const provider = encodeURIComponent(providerId)
      const url = new URL(buildApiUrl(config.public.apiBaseUrl, `/auth/oauth/${provider}/login`))
      url.searchParams.set('redirect', sanitizeInternalRedirect(redirect))
      this.oauthError = ''
      window.location.assign(url.toString())
    },
    async startOAuthLink(providerId: string, instance?: string) {
      if (typeof window === 'undefined') return
      await this.refreshUser()
      if (!this.authenticated) {
        window.location.assign('/login?redirect=%2Fprofil')
        return
      }
      if (providerId === 'mastodon') {
        const { request } = useApi()
        const result = await request<{ authorization_url: string }>('/auth/oauth/mastodon/link', {
          method: 'POST',
          body: JSON.stringify({ instance })
        })
        window.location.assign(result.authorization_url)
        return
      }
      const config = useRuntimeConfig()
      const provider = encodeURIComponent(providerId)
      this.oauthError = ''
      window.location.assign(buildApiUrl(config.public.apiBaseUrl, `/auth/oauth/${provider}/link`))
    },
    async handleOAuthCallback(redirect?: string) {
      await this.refreshUser()
      if (!this.user) {
        throw new Error('Die Anmeldung konnte nicht abgeschlossen werden.')
      }
      return sanitizeInternalRedirect(redirect)
    },
    async loadOAuthAccounts() {
      if (!this.user) {
        this.oauthAccounts = []
        return
      }
      const { request } = useApi()
      this.oauthAccounts = await request<OAuthAccount[]>('/users/me/oauth-accounts')
    },
    async refreshUser() {
      try {
        const { request } = useApi()
        // Session discovery must use the central refresh/retry path. On a fresh app
        // instance the access cookie may already be expired while the persistent
        // refresh session is still valid.
        const result = await request<AuthResponse>('/auth/session')
        this.applyAuthSession(result)
      } catch (error) {
        const code = error instanceof Error && 'code' in error && typeof error.code === 'string' ? error.code : undefined
        const statusCode = error instanceof Error && 'statusCode' in error ? error.statusCode : undefined
        if (statusCode === 401 || ['ACCOUNT_SELF_DEACTIVATED', 'ACCOUNT_DISABLED'].includes(code || '')) {
          this.clearAuthSession(false, code)
        } else {
          this.sessionUncertain = true
        }
      }
    },
    async refreshSession() {
      return await useApi().refreshSession()
    },
    applyAuthSession(result: AuthResponse) {
      this.user = result.user
      this.csrfToken = result.csrf_token
      this.sessionExpired = false
      this.sessionUncertain = false
      this.mfaChallenge = null
    },
    clearAuthSession(expired = false, blockedAuthCode?: string) {
      const wasAuthenticated = this.authenticated
      this.authGeneration += 1
      this.user = null
      this.csrfToken = null
      this.refreshing = false
      this.sessionExpired = expired && wasAuthenticated
      this.sessionUncertain = false
      this.blockedAuthCode = ['ACCOUNT_SELF_DEACTIVATED', 'ACCOUNT_DISABLED'].includes(blockedAuthCode || '') ? blockedAuthCode || '' : ''
      this.mfaChallenge = null
    },
    async login(payload: { email: string; password: string; remember?: boolean }) {
      const { request } = useApi()
      this.clearMfaChallenge()
      const result = await request<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ ...payload, remember: payload.remember ?? true }),
        retryOnUnauthorized: false
      })
      if (result.status === 'mfa_required') {
        const methods: MfaChallenge['methods'] = result.methods || ['totp', 'recovery_code']
        this.mfaChallenge = {
          token: result.challenge_token,
          preferredMethod: result.preferred_method || (methods.includes('passkey') ? 'passkey' : result.method),
          methods,
          expiresAt: Date.now() + result.expires_in * 1000
        }
        this.user = null
        this.csrfToken = null
        return result
      }
      this.applyAuthSession(result)
      return result
    },
    setMfaChallenge(token: string, expiresIn = 300, methods: MfaChallenge['methods'] = ['totp', 'recovery_code'], preferredMethod?: MfaMethod) {
      this.mfaChallenge = {
        token,
        preferredMethod: preferredMethod || (methods.includes('passkey') ? 'passkey' : methods[0] || 'totp'),
        methods,
        expiresAt: Date.now() + expiresIn * 1000
      }
    },
    async loadMfaChallenge() {
      const result = await useApi().request<MfaChallengeDetailsResponse>('/auth/mfa/challenge', {
        retryOnUnauthorized: false
      })
      this.setMfaChallenge('', result.expires_in, result.methods, result.preferred_method)
      return result
    },
    clearMfaChallenge() {
      this.mfaChallenge = null
    },
    async verifyMfa(value: string, recovery = false) {
      if (!this.mfaChallenge || this.mfaChallenge.expiresAt <= Date.now()) {
        this.clearMfaChallenge()
        throw new Error('Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.')
      }
      const method: MfaMethod = recovery ? 'recovery_code' : 'totp'
      if (!this.mfaChallenge.methods.includes(method)) {
        throw new Error('Diese Sicherheitsmethode ist für die Anmeldung nicht verfügbar.')
      }
      const factor = recovery ? normalizeRecoveryCode(value) : value.trim()
      if (recovery && !/^[A-Z0-9]{12}$/.test(factor)) {
        throw new Error('Der Wiederherstellungscode muss aus zwölf Buchstaben oder Ziffern bestehen.')
      }
      if (!recovery && !/^\d{6}$/.test(factor)) {
        throw new Error('Der Authenticator-Code muss aus sechs Ziffern bestehen.')
      }
      const { request } = useApi()
      const result = await request<AuthResponse>('/auth/mfa/verify', {
        method: 'POST',
        body: JSON.stringify({
          ...(this.mfaChallenge.token ? { challenge_token: this.mfaChallenge.token } : {}),
          ...(recovery ? { recovery_code: factor } : { code: factor })
        }),
        retryOnUnauthorized: false
      })
      this.applyAuthSession(result)
      return result
    },
    async startPasskeyLogin() {
      return await useApi().request<WebAuthnOptionsResponse>('/auth/passkeys/login/options', {
        method: 'POST', retryOnUnauthorized: false
      })
    },
    async finishPasskeyLogin(ceremonyToken: string, credential: Record<string, unknown>) {
      const result = await useApi().request<AuthResponse>('/auth/passkeys/login/verify', {
        method: 'POST',
        body: JSON.stringify({ ceremony_token: ceremonyToken, credential }),
        retryOnUnauthorized: false
      })
      this.applyAuthSession(result)
      return result
    },
    async loginWithPasskey() {
      const ceremony = await this.startPasskeyLogin()
      const credential = await authenticateWithPasskey(ceremony.options)
      return await this.finishPasskeyLogin(ceremony.ceremony_token, credential)
    },
    async startPasskeyRegistration() {
      return await useApi().request<WebAuthnOptionsResponse>('/auth/passkeys/register/options', {
        method: 'POST'
      })
    },
    async finishPasskeyRegistration(ceremonyToken: string, credential: Record<string, unknown>, name?: string) {
      const record = await useApi().request<Passkey>('/auth/passkeys/register/verify', {
        method: 'POST',
        body: JSON.stringify({ ceremony_token: ceremonyToken, credential, name: name || null })
      })
      this.passkeys.push(record)
      return record
    },
    async registerPasskey(name?: string) {
      const ceremony = await this.startPasskeyRegistration()
      const credential = await createPasskey(ceremony.options)
      return await this.finishPasskeyRegistration(ceremony.ceremony_token, credential, name)
    },
    async startPasskeyMfa() {
      if (!this.mfaChallenge || this.mfaChallenge.expiresAt <= Date.now()) {
        this.clearMfaChallenge()
        throw new Error('Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.')
      }
      if (!this.mfaChallenge.methods.includes('passkey')) {
        throw new Error('Für diese Anmeldung ist kein Passkey verfügbar.')
      }
      return await useApi().request<WebAuthnOptionsResponse>('/auth/mfa/passkey/options', {
        method: 'POST',
        body: JSON.stringify(this.mfaChallenge.token
          ? { challenge_token: this.mfaChallenge.token }
          : {}),
        retryOnUnauthorized: false
      })
    },
    async finishPasskeyMfa(ceremonyToken: string, credential: Record<string, unknown>) {
      if (!this.mfaChallenge) throw new Error('Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.')
      const result = await useApi().request<AuthResponse>('/auth/mfa/passkey/verify', {
        method: 'POST',
        body: JSON.stringify({
          ...(this.mfaChallenge.token ? { challenge_token: this.mfaChallenge.token } : {}),
          ceremony_token: ceremonyToken,
          credential
        }),
        retryOnUnauthorized: false
      })
      this.applyAuthSession(result)
      return result
    },
    async verifyMfaWithPasskey() {
      const ceremony = await this.startPasskeyMfa()
      const credential = await authenticateWithPasskey(ceremony.options)
      return await this.finishPasskeyMfa(ceremony.ceremony_token, credential)
    },
    async reauthenticateWithPasskey() {
      const ceremony = await useApi().request<WebAuthnOptionsResponse>('/auth/passkeys/reauth/options', {
        method: 'POST'
      })
      const credential = await authenticateWithPasskey(ceremony.options)
      const result = await useApi().request<AuthResponse>('/auth/passkeys/reauth/verify', {
        method: 'POST',
        body: JSON.stringify({ ceremony_token: ceremony.ceremony_token, credential })
      })
      this.applyAuthSession(result)
      return result
    },
    async loadPasskeys() {
      this.passkeys = await useApi().request<Passkey[]>('/users/me/passkeys')
      return this.passkeys
    },
    async renamePasskey(id: string, name: string) {
      const updated = await useApi().request<Passkey>(`/users/me/passkeys/${id}`, {
        method: 'PATCH', body: JSON.stringify({ name })
      })
      this.passkeys = this.passkeys.map(value => value.id === id ? updated : value)
      return updated
    },
    async deletePasskey(id: string) {
      await this.reauthenticateWithPasskey()
      await useApi().request(`/users/me/passkeys/${id}`, { method: 'DELETE' })
      this.passkeys = this.passkeys.filter(value => value.id !== id)
    },
    async signup(payload: SignupPayload) {
      const { request } = useApi()
      const result = await request<AuthResponse>('/auth/signup', {
        method: 'POST',
        body: JSON.stringify(payload),
        retryOnUnauthorized: false
      })
      this.user = result.user
      this.csrfToken = result.csrf_token
      this.sessionExpired = false
      this.sessionUncertain = false
    },
    async logout() {
      const { request } = useApi()
      this.authGeneration += 1
      this.sessionExpired = false
      this.sessionUncertain = false
      try {
        await request('/auth/logout', { method: 'POST', retryOnUnauthorized: false })
      } finally {
        this.user = null
        this.csrfToken = null
        this.refreshing = false
        this.clearMfaChallenge()
      }
    },
    async logoutAll() {
      const { request } = useApi()
      this.authGeneration += 1
      this.sessionExpired = false
      this.sessionUncertain = false
      try {
        await request('/auth/logout-all', { method: 'POST' })
      } finally {
        this.user = null
        this.csrfToken = null
        this.refreshing = false
      }
    },
    async deactivateAccount() {
      const { request } = useApi()
      await request('/users/me/deactivate', { method: 'POST', retryOnUnauthorized: false })
      this.clearAuthSession(false)
      this.oauthAccounts = []
    },
    async deleteAccount(confirmationText: string, currentPassword?: string) {
      const { request } = useApi()
      await request('/users/me', {
        method: 'DELETE',
        body: JSON.stringify({
          confirmation_text: confirmationText,
          current_password: currentPassword || null
        }),
        retryOnUnauthorized: false
      })
      this.clearAuthSession(false)
      this.oauthAccounts = []
    },
    async forgotPassword(email: string) {
      const { request } = useApi()
      await request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }), retryOnUnauthorized: false })
    },
    async resetPassword(token: string, password: string, passwordConfirm: string) {
      const { request } = useApi()
      await request('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password, password_confirm: passwordConfirm }),
        retryOnUnauthorized: false
      })
    },
    async verifyEmail(token: string) {
      const { request } = useApi()
      const result = await request<VerificationResponse>('/auth/verify-email', {
        method: 'POST',
        body: JSON.stringify({ token }),
        retryOnUnauthorized: false
      })
      await this.refreshUser()
      return result
    },
    async resendVerification() {
      const { request } = useApi()
      return await request<VerificationResponse>('/auth/resend-verification', { method: 'POST' })
    },
    async updateProfile(payload: { first_name?: string; last_name?: string; display_name?: string | null }) {
      const { request } = useApi()
      this.user = await request<AuthUser>('/users/me', { method: 'PATCH', body: JSON.stringify(payload) })
    },
    async uploadAvatar(file: File) {
      const { request } = useApi()
      const formData = new FormData()
      formData.append('avatar', file)
      this.user = await request<AuthUser>('/users/me/avatar', { method: 'POST', body: formData })
    },
    async deleteAvatar() {
      const { request } = useApi()
      this.user = await request<AuthUser>('/users/me/avatar', { method: 'DELETE' })
    },
    async unlinkOAuthAccount(provider: string) {
      const { request } = useApi()
      await request(`/users/me/oauth-accounts/${provider}`, { method: 'DELETE' })
      this.oauthAccounts = this.oauthAccounts.filter((account) => account.provider !== provider)
    },
    async completeOAuthEmail(email: string) {
      const { request } = useApi()
      const result = await request<VerificationResponse>('/auth/oauth/complete-email', {
        method: 'POST',
        body: JSON.stringify({ email })
      })
      await this.refreshUser()
      return result
    },
    async changePassword(currentPassword: string, newPassword: string, newPasswordConfirm: string) {
      const { request } = useApi()
      await request('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          new_password_confirm: newPasswordConfirm
        })
      })
      this.clearAuthSession()
    },
    async loadMfaSecurity() {
      return await useApi().request<MfaSecurityStatus>('/auth/mfa/security')
    },
    async startTotpSetup() {
      return await useApi().request<TotpSetup>('/auth/mfa/totp/setup', { method: 'POST' })
    },
    async confirmTotpSetup(code: string) {
      return await useApi().request<{ recovery_codes: string[] }>('/auth/mfa/totp/confirm', {
        method: 'POST', body: JSON.stringify({ code })
      })
    },
    async regenerateRecoveryCodes(payload: { current_password?: string, code?: string, recovery_code?: string }) {
      return await useApi().request<{ recovery_codes: string[] }>('/auth/mfa/recovery-codes', {
        method: 'POST', body: JSON.stringify(payload)
      })
    },
    async disableMfa(payload: { current_password?: string, code?: string, recovery_code?: string }) {
      await useApi().request('/auth/mfa/totp', { method: 'DELETE', body: JSON.stringify(payload) })
      this.clearAuthSession(false)
    }
  }
})
