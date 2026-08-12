import { describe, expect, it } from 'vitest'
import { buildSitemapXml } from '../server/utils/sitemap'

describe('XML sitemap', () => {
  it('renders public pages and polygon lastmod as valid escaped XML', () => {
    const xml = buildSitemapXml([
      { loc: 'https://example.org/' },
      {
        loc: 'https://example.org/flaechen/cafe-&-bar',
        lastmod: '2026-08-12T10:00:00Z'
      }
    ])

    expect(xml).toContain('<loc>https://example.org/</loc>')
    expect(xml).toContain('<loc>https://example.org/flaechen/cafe-&amp;-bar</loc>')
    expect(xml).toContain('<lastmod>2026-08-12T10:00:00Z</lastmod>')
  })

  it('contains no excluded routes when they are not supplied', () => {
    const xml = buildSitemapXml([
      { loc: 'https://example.org/' },
      { loc: 'https://example.org/ueber-das-projekt' }
    ])

    for (const excluded of ['/login', '/profil', '/impressum', '/datenschutz']) {
      expect(xml).not.toContain(excluded)
    }
  })
})
