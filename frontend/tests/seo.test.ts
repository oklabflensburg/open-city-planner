import { describe, expect, it } from 'vitest'
import {
  buildAbsoluteUrl,
  buildBreadcrumbStructuredData,
  serializeStructuredData,
  toMetaDescription
} from '~/utils/seo'

describe('SEO utilities', () => {
  it('builds normalized absolute canonical URLs', () => {
    expect(buildAbsoluteUrl('https://example.org', '/flaechen/test')).toBe('https://example.org/flaechen/test')
    expect(buildAbsoluteUrl('https://example.org/', '/')).toBe('https://example.org/')
  })

  it('normalizes and truncates user-provided descriptions', () => {
    expect(toMetaDescription('<p>Eine   Fläche</p>', 'Fallback')).toBe('Eine Fläche')
    expect(toMetaDescription('', 'Fallback')).toBe('Fallback')
    expect(toMetaDescription('abcdefghij', 'Fallback', 8)).toBe('abcdefg…')
  })

  it('serializes structured data without an executable closing script', () => {
    const serialized = serializeStructuredData({ name: '</script><script>alert(1)</script>' })

    expect(serialized).not.toContain('<script>')
    expect(serialized).toContain('\\u003c/script>')
  })

  it('builds absolute breadcrumb structured data', () => {
    const breadcrumb = buildBreadcrumbStructuredData('https://example.org', [
      { name: 'Karte', path: '/' },
      { name: 'Fläche', path: '/flaechen/test' }
    ])

    expect(breadcrumb.itemListElement).toEqual([
      expect.objectContaining({ position: 1, item: 'https://example.org/' }),
      expect.objectContaining({ position: 2, item: 'https://example.org/flaechen/test' })
    ])
  })
})
