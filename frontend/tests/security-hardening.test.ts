import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../app/${path}`, import.meta.url)),
  'utf8'
)

describe('frontend security hardening', () => {
  it('keeps OAuth MFA challenges out of the URL and browser storage', () => {
    const page = appFile('pages/auth/mfa.vue')
    const store = appFile('stores/auth.ts')
    expect(page).not.toContain('route.query.challenge')
    expect(page).toContain('HttpOnly')
    expect(store).not.toMatch(/localStorage|sessionStorage/)
  })

  it('surfaces structured admin MFA requirements with setup and re-login actions', () => {
    const api = appFile('composables/useApi.ts')
    const notice = appFile('components/admin/AdminMfaRequirement.vue')
    expect(api).toContain("error.code === 'MFA_SETUP_REQUIRED'")
    expect(api).toContain("error.code === 'MFA_REAUTH_REQUIRED'")
    expect(notice).toContain('to="/profil/sicherheit"')
    expect(notice).toContain('Mit MFA neu anmelden')
  })

  it('defines a restrictive CSP and production HSTS', () => {
    const config = readFileSync(fileURLToPath(new URL('../nuxt.config.ts', import.meta.url)), 'utf8')
    expect(config).toContain("default-src 'self'")
    expect(config).toContain("object-src 'none'")
    expect(config).toContain("frame-ancestors 'none'")
    expect(config).not.toContain('unsafe-eval')
    expect(config).toContain('strict-transport-security')
  })
})
