import { describe, expect, it } from 'vitest'
import type { AuthUser } from '~/types/auth'
import { needsEmailVerification, verificationPageCopy } from '~/utils/emailVerification'

const user = (isVerified: boolean): AuthUser => ({
  id: 'user-1',
  email: 'user@example.org',
  first_name: 'User',
  last_name: 'Example',
  is_active: true,
  is_verified: isVerified,
  is_superuser: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString()
})

describe('email verification UI state', () => {
  it('hides verify and resend prompts for a verified user', () => {
    expect(needsEmailVerification(user(true))).toBe(false)
  })

  it('shows a verify prompt only for an authenticated unverified user', () => {
    expect(needsEmailVerification(user(false))).toBe(true)
    expect(needsEmailVerification(null)).toBe(false)
  })

  it('presents already_verified as a friendly information state', () => {
    expect(verificationPageCopy('already_verified')).toEqual({
      title: 'E-Mail bereits bestätigt',
      message: 'Ihre E-Mail-Adresse wurde bereits bestätigt. Sie können sich anmelden oder zur Karte zurückkehren.'
    })
  })
})
