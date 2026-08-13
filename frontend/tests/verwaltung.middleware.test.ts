import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('verwaltung middleware', () => {
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
      user: { is_superuser: false, roles: ['VERWALTUNG'] },
      initialize: vi.fn()
    }
    vi.stubGlobal('defineNuxtRouteMiddleware', (middleware: unknown) => middleware)
    vi.stubGlobal('useAuthStore', () => authStore)
    vi.stubGlobal('navigateTo', navigateTo)
  })

  async function runMiddleware() {
    const { default: middleware } = await import('~/middleware/verwaltung')
    return await middleware({ fullPath: '/verwaltung/kennzahlen' } as never, {} as never)
  }

  it('allows users with the VERWALTUNG role', async () => {
    expect(await runMiddleware()).toBeUndefined()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('redirects anonymous users to login', async () => {
    authStore.authenticated = false
    authStore.user = null

    await runMiddleware()

    expect(navigateTo).toHaveBeenCalledWith('/login?redirect=%2Fverwaltung%2Fkennzahlen', { replace: true })
  })

  it('redirects authenticated users without the role to the map', async () => {
    authStore.user = { is_superuser: false, roles: ['USER'] }

    await runMiddleware()

    expect(navigateTo).toHaveBeenCalledWith('/', { replace: true })
  })
})
