import { describe, expect, it } from 'vitest'
import { hasOAuthProviders, oauthButtonLabel } from '~/utils/oauth'

describe('OAuth login UI', () => {
  it('shows the OAuth area only when discovery returned providers', () => {
    expect(hasOAuthProviders([])).toBe(false)
    expect(hasOAuthProviders([{ id: 'github', label: 'GitHub' }])).toBe(true)
  })

  it('uses truthful continuation labels because OAuth signs in or creates an account', () => {
    expect(oauthButtonLabel('GitHub', 'login')).toBe('Mit GitHub fortfahren')
    expect(oauthButtonLabel('Google', 'login')).toBe('Mit Google fortfahren')
    expect(oauthButtonLabel('Mastodon', 'login')).toBe('Mit Mastodon fortfahren')
  })

  it('uses the same providers for signup with signup-specific labels', () => {
    expect(oauthButtonLabel('GitHub', 'signup')).toBe('Mit GitHub fortfahren')
    expect(oauthButtonLabel('Google', 'signup')).toBe('Mit Google fortfahren')
  })
})
