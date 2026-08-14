import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('auth middleware refresh initialization', () => {
  const navigateTo = vi.fn((target: string, options?: object) => ({ target, options }))
  let authStore: {
    initialized: boolean
    authenticated: boolean
    sessionUncertain: boolean
    initialize: ReturnType<typeof vi.fn>
  }

  beforeEach(() => {
    vi.resetModules()
    navigateTo.mockClear()
    authStore = {
      initialized: false,
      authenticated: false,
      sessionUncertain: false,
      initialize: vi.fn(async () => { authStore.initialized = true })
    }
    vi.stubGlobal('defineNuxtRouteMiddleware', (middleware: unknown) => middleware)
    vi.stubGlobal('useAuthStore', () => authStore)
    vi.stubGlobal('navigateTo', navigateTo)
  })

  async function runMiddleware() {
    const { default: middleware } = await import('~/middleware/auth')
    return await middleware({ fullPath: '/profil' } as never, {} as never)
  }

  it('waits for the central session initialization before redirecting', async () => {
    authStore.initialize.mockImplementation(async () => {
      authStore.initialized = true
      authStore.authenticated = true
    })

    await runMiddleware()

    expect(authStore.initialize).toHaveBeenCalledOnce()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('keeps the protected route pending when the network leaves auth uncertain', async () => {
    authStore.initialize.mockImplementation(async () => {
      authStore.initialized = true
      authStore.sessionUncertain = true
    })

    await runMiddleware()

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('preserves the internal route after a definitively expired session', async () => {
    await runMiddleware()

    expect(navigateTo).toHaveBeenCalledWith('/login?redirect=%2Fprofil', { replace: true })
  })
})
