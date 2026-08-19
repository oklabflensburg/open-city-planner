import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  authenticateWithPasskey,
  arrayBufferToBase64url,
  base64urlToArrayBuffer,
  deserializeCreationOptions,
  deserializeRequestOptions,
  PasskeyBrowserError
} from '~/utils/webauthn'

afterEach(() => vi.unstubAllGlobals())

describe('WebAuthn utilities', () => {
  it('round-trips binary data with unpadded base64url', () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 251, 252, 253, 254, 255])

    const encoded = arrayBufferToBase64url(bytes.buffer)

    expect(encoded).not.toMatch(/[+/=]/)
    expect(new Uint8Array(base64urlToArrayBuffer(encoded))).toEqual(bytes)
  })

  it('deserializes registration challenge, user handle and excluded credentials', () => {
    const options = deserializeCreationOptions({
      challenge: 'AQID',
      rp: { id: 'localhost', name: 'Stadtplaner' },
      user: { id: 'BAUG', name: 'user@example.org', displayName: 'User' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      excludeCredentials: [{ type: 'public-key', id: 'BwgJ' }]
    })

    expect([...new Uint8Array(options.challenge)]).toEqual([1, 2, 3])
    expect([...new Uint8Array(options.user.id)]).toEqual([4, 5, 6])
    expect([...new Uint8Array(options.excludeCredentials?.[0]?.id as ArrayBuffer)]).toEqual([7, 8, 9])
  })

  it('deserializes authentication allowCredentials', () => {
    const options = deserializeRequestOptions({
      challenge: 'AQID',
      rpId: 'localhost',
      allowCredentials: [{ type: 'public-key', id: 'BAUG' }]
    })

    expect([...new Uint8Array(options.challenge)]).toEqual([1, 2, 3])
    expect([...new Uint8Array(options.allowCredentials?.[0]?.id as ArrayBuffer)]).toEqual([4, 5, 6])
  })

  it('reports an unsupported browser without calling the credential API', async () => {
    vi.stubGlobal('window', {})

    await expect(authenticateWithPasskey({ challenge: 'AQID' }))
      .rejects.toThrow('Passkeys werden von diesem Browser nicht unterstützt.')
  })

  it('turns a cancelled browser dialog into a user-facing error', async () => {
    vi.stubGlobal('window', { PublicKeyCredential: class {} })
    vi.stubGlobal('PublicKeyCredential', class {})
    vi.stubGlobal('navigator', {
      credentials: {
        get: vi.fn().mockRejectedValue(new DOMException('cancelled', 'NotAllowedError'))
      }
    })

    const result = authenticateWithPasskey({ challenge: 'AQID', rpId: 'localhost' })
    await expect(result).rejects.toThrow('Die Passkey-Anmeldung wurde abgebrochen.')
    await expect(result).rejects.toMatchObject<PasskeyBrowserError>({ code: 'PASSKEY_CANCELLED' })
  })

  it('distinguishes an explicit browser timeout from cancellation', async () => {
    vi.stubGlobal('window', { PublicKeyCredential: class {} })
    vi.stubGlobal('PublicKeyCredential', class {})
    vi.stubGlobal('navigator', {
      credentials: {
        get: vi.fn().mockRejectedValue(new DOMException('timed out', 'TimeoutError'))
      }
    })

    const result = authenticateWithPasskey({ challenge: 'AQID', rpId: 'localhost' })
    await expect(result).rejects.toThrow('Die Passkey-Anmeldung ist abgelaufen.')
    await expect(result).rejects.toMatchObject<PasskeyBrowserError>({ code: 'PASSKEY_TIMEOUT' })
  })
})
