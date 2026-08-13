import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('superuser middleware', () => {
  const navigateTo = vi.fn((target: string, options?: object) => ({ target, options }))
  let authStore: {
    initialized: boolean
    authenticated: boolean
    user: { is_superuser: boolean; roles: string[] } | null
    initialize: ReturnType<typeof vi.fn>
  }

  beforeEach(() => {
    vi.resetModules()
    navigateTo.mockClear()
    authStore = {
      initialized: true,
      authenticated: true,
      user: { is_superuser: true, roles: [] },
      initialize: vi.fn()
    }
    vi.stubGlobal('defineNuxtRouteMiddleware', (middleware: unknown) => middleware)
    vi.stubGlobal('useAuthStore', () => authStore)
    vi.stubGlobal('navigateTo', navigateTo)
  })

  async function runMiddleware() {
    const { default: middleware } = await import('~/middleware/superuser')
    return await middleware({ fullPath: '/admin/benutzer' } as never, {} as never)
  }

  it('allows superusers', async () => {
    expect(await runMiddleware()).toBeUndefined()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('redirects anonymous users to login with a safe return path', async () => {
    authStore.authenticated = false
    authStore.user = null
    await runMiddleware()
    expect(navigateTo).toHaveBeenCalledWith('/login?redirect=%2Fadmin%2Fbenutzer', { replace: true })
  })

  it('does not treat VERWALTUNG as superuser', async () => {
    authStore.user = { is_superuser: false, roles: ['VERWALTUNG'] }
    await runMiddleware()
    expect(navigateTo).toHaveBeenCalledWith('/', { replace: true })
  })
})
