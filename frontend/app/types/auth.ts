export type AuthUser = {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name?: string | null
  avatar_url?: string | null
  is_active: boolean
  is_verified: boolean
  is_superuser: boolean
  roles?: string[]
  created_at: string
  updated_at: string
  last_login_at?: string | null
}

export type AuthResponse = {
  user: AuthUser
  csrf_token: string
}

export type VerificationResponse = {
  status: 'verified' | 'already_verified' | 'verification_sent'
  code: 'EMAIL_VERIFIED' | 'EMAIL_ALREADY_VERIFIED' | 'VERIFICATION_EMAIL_SENT'
  message: string
}

export type OAuthAccount = {
  id: string
  provider: string
  provider_username?: string | null
  provider_email?: string | null
  created_at: string
  last_login_at?: string | null
}

export type OAuthProvider = {
  id: string
  label: string
}
