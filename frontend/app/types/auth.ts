import type { OAuthProviderId } from '~/types/externalProvider'

export type AuthUser = {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name?: string | null
  avatar_url?: string | null
  is_active: boolean
  is_verified: boolean
  email_pending?: boolean
  is_superuser: boolean
  roles?: string[]
  created_at: string
  updated_at: string
  last_login_at?: string | null
}

export type AuthResponse = {
  status: 'authenticated'
  user: AuthUser
  csrf_token: string
}

export type MfaChallengeResponse = {
  status: 'mfa_required'
  challenge_token: string
  method: 'totp'
  expires_in: number
}

export type LoginResponse = AuthResponse | MfaChallengeResponse

export type MfaChallenge = {
  token: string
  method: 'totp'
  expiresAt: number
}

export type MfaSecurityStatus = {
  enabled: boolean
  method: 'totp' | null
  enabled_at: string | null
  last_used_at: string | null
  recovery_codes_remaining: number
}

export type TotpSetup = {
  secret: string
  otpauth_uri: string
  issuer: string
  account_name: string
  expires_in: number
}

export type VerificationResponse = {
  status: 'verified' | 'already_verified' | 'verification_sent'
  code: 'EMAIL_VERIFIED' | 'EMAIL_ALREADY_VERIFIED' | 'VERIFICATION_EMAIL_SENT'
  message: string
}

export type OAuthAccount = {
  id: string
  provider: string
  provider_instance?: string | null
  provider_username?: string | null
  provider_email?: string | null
  provider_profile_url?: string | null
  created_at: string
  last_login_at?: string | null
}

export type OAuthProvider = {
  id: OAuthProviderId
  label: string
  requires_instance?: boolean
  default_instance?: string | null
}
