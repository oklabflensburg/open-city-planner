import type { AuthUser, VerificationResponse } from '~/types/auth'

export function needsEmailVerification(user: AuthUser | null): boolean {
  return Boolean(user && !user.is_verified)
}

export function verificationPageCopy(status: VerificationResponse['status']) {
  if (status === 'already_verified') {
    return {
      title: 'E-Mail bereits bestätigt',
      message: 'Ihre E-Mail-Adresse wurde bereits bestätigt. Sie können sich anmelden oder zur Karte zurückkehren.'
    }
  }
  return {
    title: 'E-Mail-Adresse bestätigt',
    message: 'E-Mail-Adresse erfolgreich bestätigt.'
  }
}
