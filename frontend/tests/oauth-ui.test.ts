import { describe, expect, it } from 'vitest'
import { hasOAuthProviders, oauthButtonLabel } from '~/utils/oauth'

describe('OAuth login UI', () => {
  it('shows the OAuth area only when discovery returned providers', () => {
    expect(hasOAuthProviders([])).toBe(false)
    expect(hasOAuthProviders([{ id: 'github', label: 'GitHub' }])).toBe(true)
  })

  it('creates login labels for GitHub, Google and Mastodon', () => {
    expect(oauthButtonLabel('GitHub', 'login')).toBe('Mit GitHub anmelden')
    expect(oauthButtonLabel('Google', 'login')).toBe('Mit Google anmelden')
    expect(oauthButtonLabel('Mastodon', 'login')).toBe('Mit Mastodon anmelden')
  })

  it('uses the same providers for signup with signup-specific labels', () => {
    expect(oauthButtonLabel('GitHub', 'signup')).toBe('Mit GitHub registrieren')
    expect(oauthButtonLabel('Google', 'signup')).toBe('Mit Google registrieren')
  })
})
