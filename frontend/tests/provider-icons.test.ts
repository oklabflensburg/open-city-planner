import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('external provider icons', () => {
  it('defines every provider in one decorative, non-focusable component', () => {
    const icon = appFile('components/external/ProviderIcon.vue')
    for (const provider of ['google', 'github', 'mastodon', 'openstreetmap', 'wikipedia', 'wikidata']) {
      expect(icon).toContain(`'${provider}'`)
    }
    expect(icon).toContain('aria-hidden="true"')
    expect(icon).toContain('focusable="false"')
  })

  it('does not use generic Lucide icons for GitHub or Mastodon identities', () => {
    for (const path of [
      'components/auth/OAuthLoginButtons.vue',
      'components/project/GitHubLink.vue',
      'components/project/MastodonLink.vue'
    ]) {
      const source = appFile(path)
      expect(source).not.toMatch(/\bGithub\b|\bMessageCircle\b/)
      expect(source).toContain('ProviderIcon')
    }
  })

  it('keeps OAuth labels centered with equal icon and trailing columns', () => {
    const buttons = appFile('components/auth/OAuthLoginButtons.vue')
    expect(buttons).toContain('grid-cols-[1.5rem_minmax(0,1fr)_1.5rem]')
    expect(buttons).toContain('<ProviderIcon :provider="provider.id"')
  })
})
