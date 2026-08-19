export type WebAuthnOptions = Record<string, any>

export function isPasskeySupported(): boolean {
  return typeof window !== 'undefined'
    && typeof window.PublicKeyCredential !== 'undefined'
    && typeof navigator.credentials !== 'undefined'
}

export function base64urlToArrayBuffer(value: string): ArrayBuffer {
  const padding = '='.repeat((4 - value.length % 4) % 4)
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/') + padding
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return bytes.buffer
}

export function arrayBufferToBase64url(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

export function deserializeCreationOptions(options: WebAuthnOptions): PublicKeyCredentialCreationOptions {
  return {
    ...options,
    challenge: base64urlToArrayBuffer(options.challenge),
    user: { ...options.user, id: base64urlToArrayBuffer(options.user.id) },
    excludeCredentials: options.excludeCredentials?.map((credential: WebAuthnOptions) => ({
      ...credential,
      id: base64urlToArrayBuffer(credential.id)
    }))
  } as PublicKeyCredentialCreationOptions
}

export function deserializeRequestOptions(options: WebAuthnOptions): PublicKeyCredentialRequestOptions {
  return {
    ...options,
    challenge: base64urlToArrayBuffer(options.challenge),
    allowCredentials: options.allowCredentials?.map((credential: WebAuthnOptions) => ({
      ...credential,
      id: base64urlToArrayBuffer(credential.id)
    }))
  } as PublicKeyCredentialRequestOptions
}

export function serializeCredential(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response
  const common = {
    id: credential.id,
    rawId: arrayBufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults()
  }
  if (response instanceof AuthenticatorAttestationResponse) {
    return {
      ...common,
      response: {
        clientDataJSON: arrayBufferToBase64url(response.clientDataJSON),
        attestationObject: arrayBufferToBase64url(response.attestationObject),
        transports: response.getTransports?.() || []
      }
    }
  }
  const assertion = response as AuthenticatorAssertionResponse
  return {
    ...common,
    response: {
      clientDataJSON: arrayBufferToBase64url(assertion.clientDataJSON),
      authenticatorData: arrayBufferToBase64url(assertion.authenticatorData),
      signature: arrayBufferToBase64url(assertion.signature),
      userHandle: assertion.userHandle ? arrayBufferToBase64url(assertion.userHandle) : null
    }
  }
}

export class PasskeyBrowserError extends Error {
  constructor(
    message: string,
    public readonly code: 'PASSKEY_CANCELLED' | 'PASSKEY_TIMEOUT'
  ) {
    super(message)
    this.name = 'PasskeyBrowserError'
  }
}

function passkeyBrowserError(error: unknown, elapsedMs = 0, timeoutMs = 0): Error {
  if (error instanceof DOMException && error.name === 'InvalidStateError') {
    return new Error('Dieser Passkey ist bereits registriert.')
  }
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    if (timeoutMs > 0 && elapsedMs >= timeoutMs - 250) {
      return new PasskeyBrowserError('Die Passkey-Anmeldung ist abgelaufen.', 'PASSKEY_TIMEOUT')
    }
    return new PasskeyBrowserError('Die Passkey-Anmeldung wurde abgebrochen.', 'PASSKEY_CANCELLED')
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new PasskeyBrowserError('Die Passkey-Anmeldung wurde abgebrochen.', 'PASSKEY_CANCELLED')
  }
  if (error instanceof DOMException && error.name === 'TimeoutError') {
    return new PasskeyBrowserError('Die Passkey-Anmeldung ist abgelaufen.', 'PASSKEY_TIMEOUT')
  }
  return error instanceof Error ? error : new Error('Der Passkey konnte nicht verwendet werden.')
}

export async function createPasskey(options: WebAuthnOptions): Promise<Record<string, unknown>> {
  if (!isPasskeySupported()) throw new Error('Passkeys werden von diesem Browser nicht unterstützt.')
  try {
    const credential = await navigator.credentials.create({
      publicKey: deserializeCreationOptions(options)
    }) as PublicKeyCredential | null
    if (!credential) throw new Error('Es wurde kein Passkey erstellt.')
    return serializeCredential(credential)
  } catch (error) {
    throw passkeyBrowserError(error)
  }
}

export async function authenticateWithPasskey(options: WebAuthnOptions): Promise<Record<string, unknown>> {
  if (!isPasskeySupported()) throw new Error('Passkeys werden von diesem Browser nicht unterstützt.')
  const startedAt = Date.now()
  try {
    const credential = await navigator.credentials.get({
      publicKey: deserializeRequestOptions(options)
    }) as PublicKeyCredential | null
    if (!credential) throw new Error('Es wurde kein Passkey ausgewählt.')
    return serializeCredential(credential)
  } catch (error) {
    throw passkeyBrowserError(error, Date.now() - startedAt, Number(options.timeout || 0))
  }
}
