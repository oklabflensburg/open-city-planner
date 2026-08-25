import { describe, expect, it } from 'vitest'
import {
  buildAbsoluteUrl,
  buildBreadcrumbStructuredData,
  buildCollectionPageStructuredData,
  buildFaqStructuredData,
  buildItemListStructuredData,
  buildSeoImageUrl,
  serializeStructuredData,
  toMetaDescription
} from '~/utils/seo'

describe('SEO utilities', () => {
  it('builds normalized absolute canonical URLs', () => {
    expect(buildAbsoluteUrl('https://example.org', '/flaechen/test')).toBe('https://example.org/flaechen/test')
    expect(buildAbsoluteUrl('https://example.org/', '/')).toBe('https://example.org/')
  })

  it('builds absolute social image URLs while preserving external images', () => {
    expect(buildSeoImageUrl('https://example.org', '/branding/social.png')).toBe('https://example.org/branding/social.png')
    expect(buildSeoImageUrl('https://example.org', 'https://cdn.example.net/social.png')).toBe('https://cdn.example.net/social.png')
    expect(buildSeoImageUrl('https://example.org', '')).toBeNull()
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

  it('builds collection, item list and FAQ structured data from supplied content', () => {
    const collection = buildCollectionPageStructuredData(
      'https://example.org',
      '/gebiete',
      'Gebiete',
      'Veröffentlichte Gebiete'
    )
    const itemList = buildItemListStructuredData('https://example.org', 'Stadtteile', [
      { name: 'Altstadt', path: '/gebiete/altstadt' },
      { name: 'Neustadt', path: '/gebiete/neustadt' }
    ])
    const faq = buildFaqStructuredData([
      { question: 'Wie viele Gebiete?', answer: 'So viele wie veröffentlicht sind.' }
    ])

    expect(collection).toEqual(expect.objectContaining({
      '@type': 'CollectionPage',
      url: 'https://example.org/gebiete'
    }))
    expect(itemList.numberOfItems).toBe(2)
    expect(itemList.itemListElement).toEqual([
      expect.objectContaining({ position: 1, url: 'https://example.org/gebiete/altstadt' }),
      expect.objectContaining({ position: 2, url: 'https://example.org/gebiete/neustadt' })
    ])
    expect(faq.mainEntity).toEqual([
      expect.objectContaining({
        name: 'Wie viele Gebiete?',
        acceptedAnswer: expect.objectContaining({ text: 'So viele wie veröffentlicht sind.' })
      })
    ])
  })
})
