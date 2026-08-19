import { setActivePinia, createPinia } from 'pinia'
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { useAuthStore } from '~/stores/auth'
import { ApiError } from '~/composables/useApi'
import type { AuthUser } from '~/types/auth'

const user: AuthUser = {
  id: 'user-1',
  email: 'user@example.org',
  first_name: 'User',
  last_name: 'Example',
  display_name: null,
  avatar_url: null,
  is_active: true,
  is_verified: true,
  is_superuser: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  last_login_at: null
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('does not store jwt tokens in state', () => {
    const store = useAuthStore()

    expect(Object.keys(store.$state)).not.toContain('accessToken')
    expect(Object.keys(store.$state)).not.toContain('refreshToken')
  })

  it('derives writable state from verified user', () => {
    const store = useAuthStore()

    expect(store.canWrite).toBe(false)
    store.user = user

    expect(store.authenticated).toBe(true)
    expect(store.canWrite).toBe(true)
  })

  it('keeps an MFA login challenge only in memory and does not authenticate early', async () => {
    const request = vi.fn().mockResolvedValue({
      status: 'mfa_required',
      challenge_token: 'opaque-challenge-token-value-1234567890',
      method: 'totp',
      expires_in: 300
    })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    const result = await store.login({ email: user.email, password: 'test password' })

    expect(result.status).toBe('mfa_required')
    expect(store.user).toBeNull()
    expect(store.csrfToken).toBeNull()
    expect(store.mfaChallenge?.token).toBe('opaque-challenge-token-value-1234567890')
    expect(Object.keys(store.$state)).not.toContain('localStorage')
  })

  it('applies the session only after successful MFA verification', async () => {
    const request = vi.fn().mockResolvedValue({ status: 'authenticated', user, csrf_token: 'csrf-mfa' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.setMfaChallenge('opaque-challenge-token-value-1234567890')

    await store.verifyMfa('123456')

    expect(request).toHaveBeenCalledWith('/auth/mfa/verify', expect.objectContaining({
      method: 'POST',
      retryOnUnauthorized: false
    }))
    expect(store.user).toEqual(user)
    expect(store.mfaChallenge).toBeNull()
  })

  it('starts and finishes passwordless passkey login through the existing session state', async () => {
    const options = { ceremony_token: 'ceremony-token-value-123456789012345', options: { challenge: 'AQID' } }
    const request = vi.fn()
      .mockResolvedValueOnce(options)
      .mockResolvedValueOnce({ status: 'authenticated', user, csrf_token: 'csrf-passkey' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    expect(await store.startPasskeyLogin()).toEqual(options)
    await store.finishPasskeyLogin(options.ceremony_token, { id: 'credential' })

    expect(request).toHaveBeenNthCalledWith(1, '/auth/passkeys/login/options', {
      method: 'POST', retryOnUnauthorized: false
    })
    expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({
      ceremony_token: options.ceremony_token,
      credential: { id: 'credential' }
    })
    expect(store.user).toEqual(user)
    expect(store.csrfToken).toBe('csrf-passkey')
  })

  it('binds passkey MFA ceremonies to the in-memory login challenge', async () => {
    const options = { ceremony_token: 'ceremony-token-value-123456789012345', options: { challenge: 'AQID' } }
    const request = vi.fn()
      .mockResolvedValueOnce(options)
      .mockResolvedValueOnce({ status: 'authenticated', user, csrf_token: 'csrf-mfa-passkey' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.setMfaChallenge('opaque-challenge-token-value-1234567890', 300, ['passkey', 'totp'])

    await store.startPasskeyMfa()
    await store.finishPasskeyMfa(options.ceremony_token, { id: 'credential' })

    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({
      challenge_token: 'opaque-challenge-token-value-1234567890'
    })
    expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({
      challenge_token: 'opaque-challenge-token-value-1234567890',
      ceremony_token: options.ceremony_token,
      credential: { id: 'credential' }
    })
    expect(store.user).toEqual(user)
    expect(store.mfaChallenge).toBeNull()
  })

  it('loads, registers and renames passkeys without persisting credential material', async () => {
    const first = { id: 'passkey-1', name: 'Laptop', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), last_used_at: null, device_type: 'single_device', backed_up: false, transports: ['internal'] }
    const renamed = { ...first, name: 'Arbeitslaptop' }
    const request = vi.fn()
      .mockResolvedValueOnce([first])
      .mockResolvedValueOnce(renamed)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.loadPasskeys()
    await store.renamePasskey(first.id, renamed.name)

    expect(store.passkeys).toEqual([renamed])
    expect(JSON.stringify(store.$state)).not.toContain('public_key')
    expect(JSON.stringify(store.$state)).not.toContain('credential_id')
  })

  it('rejects malformed MFA factors before sending them to the API', async () => {
    const request = vi.fn()
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.setMfaChallenge('opaque-challenge-token-value-1234567890')

    await expect(store.verifyMfa('3223322323', true)).rejects.toThrow(
      'zwölf Buchstaben oder Ziffern'
    )
    await expect(store.verifyMfa('12345')).rejects.toThrow('sechs Ziffern')
    expect(request).not.toHaveBeenCalled()
  })

  it('keeps the user unauthenticated after an invalid MFA code and clears challenges on logout', async () => {
    const request = vi.fn().mockRejectedValueOnce(new ApiError('Ungültig', { statusCode: 401, code: 'MFA_CODE_INVALID' })).mockResolvedValueOnce(undefined)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.setMfaChallenge('opaque-challenge-token-value-1234567890')

    await expect(store.verifyMfa('000000')).rejects.toThrow('Ungültig')
    expect(store.user).toBeNull()
    expect(store.mfaChallenge).not.toBeNull()
    await store.logout()
    expect(store.mfaChallenge).toBeNull()
  })

  it('keeps an existing session when initialization only fails because of the network', async () => {
    const request = vi.fn().mockRejectedValue(new TypeError('network unavailable'))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = user

    await store.initialize()

    expect(store.user).toEqual(user)
    expect(store.authenticated).toBe(true)
    expect(store.sessionUncertain).toBe(true)
    expect(store.initialized).toBe(true)
  })

  it('allows startup session discovery to refresh an expired access cookie', async () => {
    const request = vi.fn().mockResolvedValue({ user, csrf_token: 'csrf-after-refresh' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.initialize()

    expect(request).toHaveBeenCalledWith('/auth/session')
    expect(store.user).toEqual(user)
    expect(store.csrfToken).toBe('csrf-after-refresh')
  })

  it('clears a stale session and preserves a self-deactivation code for login UX', async () => {
    const request = vi.fn().mockRejectedValue(new ApiError('disabled', {
      statusCode: 403,
      code: 'ACCOUNT_SELF_DEACTIVATED'
    }))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = user

    await store.refreshUser()

    expect(store.user).toBeNull()
    expect(store.blockedAuthCode).toBe('ACCOUNT_SELF_DEACTIVATED')
    expect(store.sessionUncertain).toBe(false)
  })

  it('refreshes the global user after successful email verification', async () => {
    const verifiedUser = { ...user, is_verified: true }
    const request = vi.fn()
      .mockResolvedValueOnce({
        status: 'verified',
        code: 'EMAIL_VERIFIED',
        message: 'E-Mail-Adresse bestätigt.'
      })
      .mockResolvedValueOnce({ user: verifiedUser, csrf_token: 'csrf-new' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = { ...user, is_verified: false }

    const result = await store.verifyEmail('a-valid-random-token')

    expect(result.status).toBe('verified')
    expect(request).toHaveBeenNthCalledWith(1, '/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token: 'a-valid-random-token' }),
      retryOnUnauthorized: false
    })
    expect(request).toHaveBeenNthCalledWith(2, '/auth/session')
    expect(store.user?.is_verified).toBe(true)
    expect(store.canWrite).toBe(true)
  })

  it('returns the idempotent already-verified response and refreshes the user', async () => {
    const request = vi.fn()
      .mockResolvedValueOnce({
        status: 'already_verified',
        code: 'EMAIL_ALREADY_VERIFIED',
        message: 'Die E-Mail-Adresse wurde bereits bestätigt.'
      })
      .mockResolvedValueOnce({ user, csrf_token: 'csrf-new' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    const result = await store.verifyEmail('an-already-used-token')

    expect(result.status).toBe('already_verified')
    expect(store.user?.is_verified).toBe(true)
  })

  it('updates user avatar after upload', async () => {
    const request = vi.fn().mockResolvedValue({ ...user, avatar_url: '/api/v1/media/avatars/new.webp' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.uploadAvatar(new File(['avatar'], 'avatar.png', { type: 'image/png' }))

    expect(request).toHaveBeenCalledWith('/users/me/avatar', expect.objectContaining({
      method: 'POST',
      body: expect.any(FormData)
    }))
    expect(store.user?.avatar_url).toBe('/api/v1/media/avatars/new.webp')
  })

  it('clears user avatar after delete', async () => {
    const request = vi.fn().mockResolvedValue({ ...user, avatar_url: null })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = { ...user, avatar_url: '/api/v1/media/avatars/old.webp' }

    await store.deleteAvatar()

    expect(request).toHaveBeenCalledWith('/users/me/avatar', { method: 'DELETE' })
    expect(store.user?.avatar_url).toBeNull()
  })

  it('deactivates the current account and clears local authentication only after success', async () => {
    const request = vi.fn().mockResolvedValue({ message: 'Das Konto wurde deaktiviert.' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = user

    await store.deactivateAccount()

    expect(request).toHaveBeenCalledWith('/users/me/deactivate', {
      method: 'POST',
      retryOnUnauthorized: false
    })
    expect(store.user).toBeNull()
  })

  it('sends only confirmation and optional password when deleting the current account', async () => {
    const request = vi.fn().mockResolvedValue({ message: 'Das Konto wurde dauerhaft gelöscht.' })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = user

    await store.deleteAccount('LÖSCHEN', 'current password')

    expect(request).toHaveBeenCalledWith('/users/me', {
      method: 'DELETE',
      body: JSON.stringify({
        confirmation_text: 'LÖSCHEN',
        current_password: 'current password'
      }),
      retryOnUnauthorized: false
    })
    expect(store.user).toBeNull()
  })

  it('loads oauth accounts for authenticated user', async () => {
    const request = vi.fn().mockResolvedValue([{ id: 'oauth-1', provider: 'github', provider_username: 'kunstbube', provider_email: null, created_at: new Date().toISOString(), last_login_at: null }])
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.user = user

    await store.loadOAuthAccounts()

    expect(request).toHaveBeenCalledWith('/users/me/oauth-accounts')
    expect(store.oauthAccounts).toHaveLength(1)
    expect(store.oauthAccounts[0].provider).toBe('github')
  })

  it('loads configured oauth providers', async () => {
    const request = vi.fn().mockResolvedValue([
      { id: 'github', label: 'GitHub' },
      { id: 'google', label: 'Google' }
    ])
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.loadProviders()

    expect(request).toHaveBeenCalledWith('/auth/oauth/providers', { retryOnUnauthorized: false })
    expect(store.oauthProviders).toEqual([
      { id: 'github', label: 'GitHub' },
      { id: 'google', label: 'Google' }
    ])
    expect(store.oauthProvidersLoaded).toBe(true)
  })

  it('keeps the OAuth area empty when no providers are configured', async () => {
    const request = vi.fn().mockResolvedValue([])
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.loadProviders()
    await store.loadProviders()

    expect(store.oauthProviders).toEqual([])
    expect(store.oauthProvidersLoaded).toBe(true)
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('keeps password login available when provider discovery fails', async () => {
    const request = vi.fn().mockRejectedValue(new Error('network unavailable'))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()

    await store.loadProviders()

    expect(store.oauthProviders).toEqual([])
    expect(store.oauthError).toBe('OAuth-Anbieter konnten nicht geladen werden.')
    expect(store.oauthProvidersLoading).toBe(false)
  })

  it('starts oauth login with sanitized redirect', () => {
    const assign = vi.fn()
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://localhost:8000/api/v1' } }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()

    store.startOAuthLogin('github', 'https://evil.example')

    expect(assign).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/oauth/github/login?redirect=%2F')
  })

  it('normalizes the API base URL and preserves an internal Google redirect', () => {
    const assign = vi.fn()
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://localhost:8000/api/v1/' } }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()

    store.startOAuthLogin('google', '/meine-flaechen?status=aktiv')

    expect(assign).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/oauth/google/login?redirect=%2Fmeine-flaechen%3Fstatus%3Daktiv')
  })

  it('starts federated Mastodon login through the instance-aware API', async () => {
    const assign = vi.fn()
    const request = vi.fn().mockResolvedValue({ authorization_url: 'https://social.example/oauth/authorize?state=opaque' })
    vi.stubGlobal('useApi', () => ({ request }))
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://localhost:8000/api/v1' } }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()

    await store.startOAuthLogin('mastodon', 'https://evil.example', '@user@social.example')

    expect(request).toHaveBeenCalledWith('/auth/oauth/mastodon/start', {
      method: 'POST',
      body: JSON.stringify({ instance: '@user@social.example', redirect: '/' }),
      retryOnUnauthorized: false
    })
    expect(assign).toHaveBeenCalledWith('https://social.example/oauth/authorize?state=opaque')
  })

  it('links Mastodon directly from the authenticated profile', async () => {
    const assign = vi.fn()
    const request = vi.fn()
      .mockResolvedValueOnce({ user, csrf_token: 'csrf-current' })
      .mockResolvedValueOnce({ authorization_url: 'https://social.example/oauth/authorize' })
    vi.stubGlobal('useApi', () => ({ request }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()
    store.user = user

    await store.startOAuthLink('mastodon', 'social.example')

    expect(request).toHaveBeenNthCalledWith(2, '/auth/oauth/mastodon/link', {
      method: 'POST',
      body: JSON.stringify({ instance: 'social.example' })
    })
    expect(assign).toHaveBeenCalledWith('https://social.example/oauth/authorize')
  })

  it.each(['github', 'google'])('starts authenticated %s account linking after a session check', async (provider) => {
    const assign = vi.fn()
    const request = vi.fn().mockResolvedValue({ user, csrf_token: 'csrf-current' })
    vi.stubGlobal('useApi', () => ({ request }))
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://localhost:8000/api/v1/' } }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()
    store.user = user

    await store.startOAuthLink(provider)

    expect(request).toHaveBeenCalledWith('/auth/session')
    expect(assign).toHaveBeenCalledWith(`http://localhost:8000/api/v1/auth/oauth/${provider}/link`)
  })

  it('sends only anonymous account-link attempts to login', async () => {
    const assign = vi.fn()
    const request = vi.fn().mockRejectedValue(Object.assign(new Error('auth required'), { statusCode: 401 }))
    vi.stubGlobal('useApi', () => ({ request }))
    vi.stubGlobal('window', { location: { assign } })
    const store = useAuthStore()

    await store.startOAuthLink('github')

    expect(assign).toHaveBeenCalledWith('/login?redirect=%2Fprofil')
  })

  it('unlinks oauth account from store', async () => {
    const request = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAuthStore()
    store.oauthAccounts = [
      { id: 'oauth-1', provider: 'github', provider_username: 'kunstbube', provider_email: null, created_at: new Date().toISOString(), last_login_at: null },
      { id: 'oauth-2', provider: 'google', provider_username: 'user@example.org', provider_email: 'user@example.org', created_at: new Date().toISOString(), last_login_at: null }
    ]

    await store.unlinkOAuthAccount('github')

    expect(request).toHaveBeenCalledWith('/users/me/oauth-accounts/github', { method: 'DELETE' })
    expect(store.oauthAccounts.map((account) => account.provider)).toEqual(['google'])
  })
})
