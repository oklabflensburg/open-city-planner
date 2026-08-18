import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { blockedLoginDetailRows } from '~/utils/auditLog'
import { getAuthErrorPresentation } from '~/utils/authErrors'

const appFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../app/${path}`, import.meta.url)),
  'utf8'
)

describe('deactivated account authentication UX', () => {
  it('distinguishes self-deactivation from a neutral administrative disablement', () => {
    expect(getAuthErrorPresentation('ACCOUNT_SELF_DEACTIVATED')).toMatchObject({
      title: 'Ihr Konto ist deaktiviert',
      accountStatus: true,
      showSupportLink: true
    })
    expect(getAuthErrorPresentation('ACCOUNT_DISABLED')).toMatchObject({
      title: 'Dieses Konto ist derzeit deaktiviert',
      accountStatus: true
    })
    expect(getAuthErrorPresentation('ACCOUNT_DISABLED')?.message).not.toContain('selbst')
  })

  it('uses structured codes, an inline status card and cleans the query via replace', () => {
    const login = appFile('pages/login.vue')
    expect(login).toContain('getAuthErrorPresentation')
    expect(login).toContain('role="status"')
    expect(login).toContain('Kontakt aufnehmen')
    expect(login).toContain("delete query.auth_error")
    expect(login).toContain('await router.replace({ query })')
    expect(login).not.toContain("message.includes('deaktiviert')")
  })

  it('renders blocked-login audit metadata with understandable labels', () => {
    expect(blockedLoginDetailRows({ reason: 'SELF_DEACTIVATED', provider: 'password' })).toEqual([
      { label: 'Grund', value: 'Selbst deaktiviert' },
      { label: 'Anmeldemethode', value: 'E-Mail / Passwort' }
    ])
    expect(blockedLoginDetailRows({ reason: 'SELF_DEACTIVATED', provider: 'mastodon' })[1]?.value).toBe('Mastodon')
  })
})
