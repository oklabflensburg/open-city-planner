import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('Mastodon SSO UI', () => {
  it('uses the shared accessible modal instead of native prompts', () => {
    const dialog = appFile('components/auth/MastodonInstanceDialog.vue')
    expect(dialog).toContain('<AppModal')
    expect(dialog).toContain('data-autofocus')
    expect(dialog).toContain('aria-describedby="mastodon-instance-help mastodon-instance-error"')
    expect(dialog).not.toContain('prompt(')
    expect(dialog).not.toContain('alert(')
  })

  it('offers instance selection for login and authenticated account linking', () => {
    const login = appFile('components/auth/OAuthLoginButtons.vue')
    const accounts = appFile('components/auth/OAuthAccountList.vue')
    expect(login).toContain('<MastodonInstanceDialog')
    expect(login).toContain('mode="login"')
    expect(accounts).toContain('<MastodonInstanceDialog')
    expect(accounts).toContain('mode="link"')
    expect(accounts).not.toContain('/login?redirect=/profil')
  })

  it('shows controlled email onboarding for identities without provider email', () => {
    const profile = appFile('pages/profil/index.vue')
    expect(profile).toContain('Fast geschafft')
    expect(profile).toContain('authStore.completeOAuthEmail')
    expect(profile).toContain('email_pending')
  })
})
