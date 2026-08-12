import { describe, expect, it } from 'vitest'
import { sanitizeInternalRedirect } from '~/utils/redirect'

describe('sanitizeInternalRedirect', () => {
  it('allows relative internal paths', () => {
    expect(sanitizeInternalRedirect('/')).toBe('/')
    expect(sanitizeInternalRedirect('/profil')).toBe('/profil')
    expect(sanitizeInternalRedirect('/meine-flaechen?filter=1')).toBe('/meine-flaechen?filter=1')
    expect(sanitizeInternalRedirect('/?polygon=123')).toBe('/?polygon=123')
  })

  it('rejects external and unsafe redirects', () => {
    expect(sanitizeInternalRedirect('https://example.org')).toBe('/')
    expect(sanitizeInternalRedirect('//example.org')).toBe('/')
    expect(sanitizeInternalRedirect('/\\example.org')).toBe('/')
    expect(sanitizeInternalRedirect('javascript:alert(1)')).toBe('/')
    expect(sanitizeInternalRedirect('data:text/html,test')).toBe('/')
    expect(sanitizeInternalRedirect(null)).toBe('/')
  })

  it('uses a caller-provided fallback', () => {
    expect(sanitizeInternalRedirect('https://example.org', '/profil')).toBe('/profil')
    expect(sanitizeInternalRedirect(undefined, '/profil')).toBe('/profil')
  })
})
