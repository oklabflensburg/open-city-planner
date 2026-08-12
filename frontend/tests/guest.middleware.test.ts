import { beforeEach, describe, expect, it, vi } from 'vitest'

type AuthState = {
  initialized: boolean
  authenticated: boolean
  initialize: ReturnType<typeof vi.fn>
}

describe('guest middleware', () => {
  let authStore: AuthState
  const navigateTo = vi.fn((target: string, options?: object) => ({ target, options }))

  beforeEach(() => {
    vi.resetModules()
    authStore = {
      initialized: true,
      authenticated: false,
      initialize: vi.fn()
    }
    vi.stubGlobal('defineNuxtRouteMiddleware', (middleware: unknown) => middleware)
    vi.stubGlobal('useAuthStore', () => authStore)
    vi.stubGlobal('navigateTo', navigateTo)
    navigateTo.mockClear()
  })

  async function runMiddleware(redirect?: unknown) {
    const { default: middleware } = await import('~/middleware/guest')
    return await middleware({ query: { redirect } } as never, {} as never)
  }

  it('allows anonymous users to open login', async () => {
    expect(await runMiddleware()).toBeUndefined()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('waits for initialization before deciding', async () => {
    authStore.initialized = false
    authStore.initialize.mockImplementation(async () => {
      authStore.initialized = true
    })

    await runMiddleware()

    expect(authStore.initialize).toHaveBeenCalledOnce()
  })

  it('redirects authenticated users to the profile by default', async () => {
    authStore.authenticated = true

    await runMiddleware()

    expect(navigateTo).toHaveBeenCalledWith('/profil', { replace: true })
  })

  it('honors a safe internal redirect for authenticated users', async () => {
    authStore.authenticated = true

    await runMiddleware('/meine-flaechen')

    expect(navigateTo).toHaveBeenCalledWith('/meine-flaechen', { replace: true })
  })

  it('rejects external redirects for authenticated users', async () => {
    authStore.authenticated = true

    await runMiddleware('https://evil.example')

    expect(navigateTo).toHaveBeenCalledWith('/profil', { replace: true })
  })
})
