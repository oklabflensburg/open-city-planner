import type { MfaMethod } from '~/types/auth'

export function normalizeRecoveryCode(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, '')
}

export function formatRecoveryCode(value: string): string {
  return normalizeRecoveryCode(value).slice(0, 12).match(/.{1,4}/g)?.join('-') || ''
}

export function preferredAvailableMethod(
  methods: MfaMethod[],
  preferred: MfaMethod,
  passkeySupported: boolean
): MfaMethod | null {
  const available = methods.filter(method => method !== 'passkey' || passkeySupported)
  if (available.includes(preferred)) return preferred
  return available.find(method => method === 'totp')
    || available.find(method => method === 'recovery_code')
    || available.find(method => method === 'passkey')
    || null
}
