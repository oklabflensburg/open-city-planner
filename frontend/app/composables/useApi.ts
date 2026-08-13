import { buildApiUrl } from '~/utils/apiUrl'

type ApiOptions = RequestInit & {
  retryOnUnauthorized?: boolean
}

let refreshPromise: Promise<boolean> | null = null

export const useApi = () => {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()

  async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
    const headers = new Headers(options.headers)
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    if (options.body && !isFormData && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (import.meta.server && !headers.has('Cookie')) {
      const requestHeaders = useRequestHeaders(['cookie'])
      if (requestHeaders.cookie) {
        headers.set('Cookie', requestHeaders.cookie)
      }
    }
    const csrf = csrfToken(options.method)
    if (csrf) {
      headers.set('X-CSRF-Token', csrf)
    }

    const response = await fetch(buildApiUrl(config.public.apiBaseUrl, path), {
      ...options,
      credentials: 'include',
      headers
    })

    if (response.status === 401 && options.retryOnUnauthorized !== false && path !== '/auth/refresh') {
      const refreshed = await refreshOnce()
      if (refreshed) {
        return request<T>(path, { ...options, retryOnUnauthorized: false })
      }
    }

    if (!response.ok) {
      throw await apiError(response)
    }

    if (response.status === 204) {
      return undefined as T
    }

    return await response.json() as T
  }

  async function refreshOnce() {
    if (!refreshPromise) {
      refreshPromise = authStore.refreshSession().finally(() => {
        refreshPromise = null
      })
    }
    return await refreshPromise
  }

  function csrfToken(method = 'GET') {
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) {
      return null
    }
    const token = authStore.csrfToken || useCookie<string | null>('ocm_csrf_token').value
    return token || null
  }

  async function apiError(response: Response) {
    try {
      const body = await response.json()
      const error = body?.detail?.error || body?.error
      return Object.assign(
        new Error(error?.message || body?.detail || `API request failed with ${response.status}`),
        { statusCode: response.status, details: body?.detail }
      )
    } catch {
      return Object.assign(new Error(`API request failed with ${response.status}`), {
        statusCode: response.status
      })
    }
  }

  return { request }
}
