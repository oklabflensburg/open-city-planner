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
})
