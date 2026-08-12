import { describe, expect, it } from 'vitest'
import { buildApiUrl } from '~/utils/apiUrl'

describe('API URL construction', () => {
  it('joins base URL and path with exactly one slash', () => {
    expect(buildApiUrl('http://localhost:8000/api/v1/', '/auth/oauth/providers'))
      .toBe('http://localhost:8000/api/v1/auth/oauth/providers')
    expect(buildApiUrl('http://localhost:8000/api/v1', 'auth/oauth/providers'))
      .toBe('http://localhost:8000/api/v1/auth/oauth/providers')
  })
})
