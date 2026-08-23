import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { formatRecoveryCode, normalizeRecoveryCode, preferredAvailableMethod } from '~/utils/mfa'

const component = readFileSync(
  fileURLToPath(new URL('../app/components/auth/MfaChallengeForm.vue', import.meta.url)),
  'utf8'
)

describe('MFA method selection', () => {
  it('uses the backend preference and falls back only to an available browser method', () => {
    expect(preferredAvailableMethod(['passkey', 'totp', 'recovery_code'], 'passkey', true)).toBe('passkey')
    expect(preferredAvailableMethod(['passkey', 'totp', 'recovery_code'], 'passkey', false)).toBe('totp')
    expect(preferredAvailableMethod(['recovery_code'], 'recovery_code', false)).toBe('recovery_code')
    expect(preferredAvailableMethod(['passkey'], 'passkey', false)).toBeNull()
  })

  it('normalizes and formats pasted recovery codes', () => {
    expect(normalizeRecoveryCode('abcd efgh-ijkl')).toBe('ABCDEFGHIJKL')
    expect(formatRecoveryCode('abcd efgh-ijkl')).toBe('ABCD-EFGH-IJKL')
  })

  it('renders only backend-provided methods and preserves alternatives after passkey cancellation', () => {
    expect(component).toContain("authStore.mfaChallenge?.methods")
    expect(component).toContain("method !== 'passkey' || passkeySupported.value")
    expect(component).toContain("cause instanceof PasskeyBrowserError")
    expect(component).toContain('Passkey erneut versuchen')
    expect(component).toContain('Authenticator-App verwenden')
    expect(component).toContain('Wiederherstellungscode verwenden')
    expect(component).toContain('role="alert"')
    expect(component).toContain('role="status"')
  })

  it('presents alternative methods as one-column accessible selection cards', () => {
    expect(component).toContain('data-mfa-challenge')
    expect(component).toContain('grid min-w-0 gap-5')
    expect(component).toContain('data-mfa-method-options')
    expect(component).toContain('data-mfa-method-option')
    expect(component).toContain('class="grid gap-2" data-mfa-method-options')
    expect(component).not.toContain('sm:grid-cols-2')
    expect(component).toContain('min-h-16 min-w-0 w-full')
    expect(component).toContain(':disabled="busy"')
    expect(component).toContain(':aria-label="methodLabel(method)"')
    expect(component).toContain(':aria-describedby="methodDescriptionId(method)"')
  })

  it('provides concise titles, descriptions and existing icon components for every method', () => {
    expect(component).toContain("passkey: 'Passkey'")
    expect(component).toContain("totp: 'Authenticator-App'")
    expect(component).toContain("recovery_code: 'Wiederherstellungscode'")
    expect(component).toContain('Mit Gerät oder Sicherheitsschlüssel bestätigen')
    expect(component).toContain('Sechsstelligen Code aus Ihrer Authenticator-App eingeben')
    expect(component).toContain('Einen gespeicherten Wiederherstellungscode verwenden')
    expect(component).toContain('KeyRound')
    expect(component).toContain('ShieldCheck')
    expect(component).toContain('LifeBuoy')
    expect(component).toContain('ChevronRight')
    expect(component).toContain('ArrowLeft')
  })
})
