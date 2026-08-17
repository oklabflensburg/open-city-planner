import { defineStore } from 'pinia'
import type { AuthResponse, AuthUser, OAuthAccount, OAuthProvider, VerificationResponse } from '~/types/auth'
import { buildApiUrl } from '~/utils/apiUrl'
import { sanitizeInternalRedirect } from '~/utils/redirect'

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
    oauthAccounts: [] as OAuthAccount[]
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
      } catch (error) {
        this.oauthProviders = []
        this.oauthError = 'OAuth-Anbieter konnten nicht geladen werden.'
        if (import.meta.dev) {
          console.warn('Failed to load OAuth providers', error)
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
        const result = await request<AuthResponse>('/auth/session', { retryOnUnauthorized: false })
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
    },
    async login(payload: { email: string; password: string; remember?: boolean }) {
      const { request } = useApi()
      const result = await request<AuthResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ ...payload, remember: payload.remember ?? true }),
        retryOnUnauthorized: false
      })
      this.user = result.user
      this.csrfToken = result.csrf_token
      this.sessionExpired = false
      this.sessionUncertain = false
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
    }
  }
})
