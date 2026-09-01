import { describe, expect, it } from 'vitest'
import { buildSitemapXml, moduleSitemapPaths } from '../server/utils/sitemap'

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

  it('includes module routes only for supplied enabled contributions', () => {
    expect(moduleSitemapPaths([])).toEqual([])
    expect(moduleSitemapPaths([{
      staticRoutes: ['/gebiete'],
      dynamicRoutes: [{
        route: '/gebiete/:slug',
        entries: [{ slug: 'altstadt-15630273', updated_at: '2026-09-01T10:00:00Z' }]
      }]
    }])).toEqual([
      { path: '/gebiete' },
      {
        path: '/gebiete/altstadt-15630273',
        lastmod: '2026-09-01T10:00:00Z'
      }
    ])
  })

  it('keeps the public Open Data collection address stable', async () => {
    const source = await import('../server/routes/sitemap.xml.ts?raw').then(module => module.default)
    expect(source).toContain("'/open-data'")
    expect(source).toContain('frontendSitemapContributions')
    expect(source).toContain('moduleSitemapPaths')
    expect(source).not.toContain("'/gebiete'")
    expect(source).not.toContain('/analysis-areas/sitemap')
  })
})
