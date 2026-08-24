import type { AuthResponse } from '~/types/auth'
import { buildApiUrl } from '~/utils/apiUrl'
import { executeWithRefreshRetry, singleFlightRefresh } from '~/utils/authRetry'

export type ApiOptions = RequestInit & {
  retryOnUnauthorized?: boolean
}

export class ApiError extends Error {
  statusCode?: number
  code?: string
  details?: unknown

  constructor(message: string, options: { statusCode?: number, code?: string, details?: unknown } = {}) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = options.statusCode
    this.code = options.code
    this.details = options.details
  }
}

const NO_REFRESH_PATHS = [
  '/auth/login',
  '/auth/signup',
  '/auth/refresh',
  '/auth/logout',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/oauth/'
]
const REFRESHABLE_CODES = new Set(['ACCESS_TOKEN_EXPIRED', 'AUTH_REQUIRED'])
const DEFINITIVE_AUTH_CODES = new Set([
  'ACCESS_TOKEN_INVALID',
  'REFRESH_TOKEN_EXPIRED',
  'REFRESH_TOKEN_INVALID',
  'REFRESH_TOKEN_MISSING',
  'REFRESH_TOKEN_REUSE_DETECTED',
  'SESSION_REVOKED',
  'USER_INACTIVE',
  'ACCOUNT_SELF_DEACTIVATED',
  'ACCOUNT_DISABLED'
])

export const useApi = () => {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const adminMfaRequirement = useState<'MFA_SETUP_REQUIRED' | 'MFA_REAUTH_REQUIRED' | null>('admin-mfa-requirement', () => null)
  const forwardedCookie = import.meta.server ? useRequestHeaders(['cookie']).cookie : undefined
  const forwardedRequestId = import.meta.server ? useRequestHeaders(['x-request-id'])['x-request-id'] : undefined

  async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
    return execute<T>(path, options)
  }

  async function execute<T>(path: string, options: ApiOptions): Promise<T> {
    const { retryOnUnauthorized = true, ...fetchOptions } = options
    let attemptCount = 0
    const response = await executeWithRefreshRetry({
      send: () => {
        attemptCount += 1
        return rawRequest(path, fetchOptions)
      },
      failure: authFailure,
      refresh: refreshOnce,
      canRefresh: failure => retryOnUnauthorized && shouldRefresh(path, failure.code)
    })

    if (response.status === 401) {
      const error = await apiError(response)
      if ((attemptCount > 1 || DEFINITIVE_AUTH_CODES.has(error.code || '')) && authStore.authenticated) {
        authStore.clearAuthSession(true)
      }
      throw error
    }

    if (!response.ok) {
      const error = await apiError(response)
      if (path.startsWith('/admin/') && (error.code === 'MFA_SETUP_REQUIRED' || error.code === 'MFA_REAUTH_REQUIRED')) {
        adminMfaRequirement.value = error.code
      }
      if (DEFINITIVE_AUTH_CODES.has(error.code || '') && authStore.authenticated) {
        authStore.clearAuthSession(false, error.code)
      }
      throw error
    }
    if (path.startsWith('/admin/')) adminMfaRequirement.value = null
    if (response.status === 204) return undefined as T
    return await response.json() as T
  }

  async function rawRequest(path: string, options: RequestInit = {}) {
    const headers = new Headers(options.headers)
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    if (options.body && !isFormData && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (import.meta.server && !headers.has('Cookie')) {
      if (forwardedCookie) headers.set('Cookie', forwardedCookie)
    }
    if (!headers.has('X-Request-ID')) {
      headers.set('X-Request-ID', forwardedRequestId || crypto.randomUUID())
    }
    const csrf = csrfToken(options.method)
    if (csrf) headers.set('X-CSRF-Token', csrf)

    return await fetch(buildApiUrl(config.public.apiBaseUrl, path), {
      ...options,
      credentials: 'include',
      headers
    })
  }

  function shouldRefresh(path: string, code?: string) {
    if (import.meta.server || NO_REFRESH_PATHS.some(excluded => path === excluded || path.startsWith(excluded))) {
      return false
    }
    return REFRESHABLE_CODES.has(code || '')
  }

  async function refreshOnce() {
    if (!import.meta.client) return false
    return await singleFlightRefresh(performRefresh)
  }

  async function performRefresh() {
    const generation = authStore.authGeneration
    authStore.refreshing = true
    try {
      const response = await rawRequest('/auth/refresh', { method: 'POST' })
      if (!response.ok) {
        const error = await apiError(response)
        if (DEFINITIVE_AUTH_CODES.has(error.code || '')) {
          const isBlockedAccount = ['ACCOUNT_SELF_DEACTIVATED', 'ACCOUNT_DISABLED'].includes(error.code || '')
          authStore.clearAuthSession(authStore.authenticated && !isBlockedAccount, error.code)
        }
        throw error
      }
      const result = await response.json() as AuthResponse
      if (generation !== authStore.authGeneration) return false
      authStore.applyAuthSession(result)
      return true
    } finally {
      if (generation === authStore.authGeneration) authStore.refreshing = false
    }
  }

  function csrfToken(method = 'GET') {
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) return null
    const token = authStore.csrfToken || useCookie<string | null>('ocm_csrf_token').value
    return token || null
  }

  async function authFailure(response: Response) {
    if (response.status !== 401) return { status: response.status }
    try {
      const body = await response.clone().json()
      return { status: response.status, code: body?.detail?.error?.code || body?.error?.code }
    } catch {
      return { status: response.status }
    }
  }

  async function apiError(response: Response) {
    try {
      const body = await response.json()
      const error = body?.detail?.error || body?.error
      return new ApiError(error?.message || body?.detail || `Die API-Anfrage ist mit Status ${response.status} fehlgeschlagen.`, {
        statusCode: response.status,
        code: error?.code,
        details: body?.detail
      })
    } catch (cause) {
      if (cause instanceof ApiError) return cause
      return new ApiError(`Die API-Anfrage ist mit Status ${response.status} fehlgeschlagen.`, { statusCode: response.status })
    }
  }

  return { request, refreshSession: refreshOnce }
}
