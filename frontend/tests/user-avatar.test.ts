import { describe, expect, it } from 'vitest'
import { getUserInitials, resolveAvatarUrl } from '~/utils/user'
import type { AuthUser } from '~/types/auth'

const baseUser: AuthUser = {
  id: 'user-1',
  email: 'user@example.org',
  first_name: 'User',
  last_name: 'Example',
  display_name: null,
  avatar_url: null,
  is_active: true,
  is_verified: true,
  is_superuser: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  last_login_at: null
}

describe('user avatar utilities', () => {
  it('uses display name initials first', () => {
    expect(getUserInitials({ ...baseUser, display_name: 'Open City' })).toBe('OC')
  })

  it('falls back to first and last name initials', () => {
    expect(getUserInitials(baseUser)).toBe('UE')
  })

  it('falls back to email initial', () => {
    expect(getUserInitials({ ...baseUser, first_name: '', last_name: '' })).toBe('U')
  })

  it('resolves relative media URLs against the API origin', () => {
    expect(resolveAvatarUrl('/api/v1/media/avatars/a.webp', { apiBaseUrl: 'http://localhost:8000/api/v1' })).toBe('http://localhost:8000/api/v1/media/avatars/a.webp')
  })

  it('prefers explicit media base URL', () => {
    expect(resolveAvatarUrl('/api/v1/media/avatars/a.webp', {
      apiBaseUrl: 'http://localhost:8000/api/v1',
      mediaBaseUrl: 'https://media.example.org'
    })).toBe('https://media.example.org/api/v1/media/avatars/a.webp')
  })
})
