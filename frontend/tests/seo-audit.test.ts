import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  auditIndexableHtml,
  auditNoindexHtml,
  hasLocalHost,
  sitemapLocations
} from '../scripts/seo-audit-lib.mjs'
import {
  DYNAMIC_PUBLIC_ROUTES,
  NOINDEX_ROUTES,
  NOT_FOUND_ROUTES,
  REDIRECT_ROUTES,
  SOCIAL_PREVIEW_ROUTES
} from '../scripts/seo-route-matrix.mjs'

const expectedUrl = 'https://stadtplaner.example.test/test'

function validHtml(overrides: {
  title?: string
  description?: string
  robots?: string
  canonical?: string
  ogUrl?: string
  jsonLd?: string
} = {}) {
  const title = overrides.title ?? 'Testseite – OK Lab Flensburg'
  const description = overrides.description ?? 'Eine aussagekräftige Beschreibung der Testseite.'
  const robots = overrides.robots ?? 'index,follow'
  const canonical = overrides.canonical ?? expectedUrl
  const ogUrl = overrides.ogUrl ?? canonical
  const jsonLd = overrides.jsonLd ?? JSON.stringify({ '@context': 'https://schema.org', '@type': 'WebPage', url: canonical })
  return `<!doctype html><html><head><title>${title}</title><meta name="description" content="${description}"><meta name="robots" content="${robots}"><link rel="canonical" href="${canonical}"><meta property="og:title" content="${title}"><meta property="og:description" content="${description}"><meta property="og:url" content="${ogUrl}"><meta property="og:type" content="website"><meta property="og:site_name" content="OK Lab Flensburg"><meta name="twitter:card" content="summary"><meta name="twitter:title" content="${title}"><meta name="twitter:description" content="${description}"><script type="application/ld+json">${jsonLd}</script></head><body><h1>Testseite</h1></body></html>`
}

describe('SEO audit helpers', () => {
  it('accepts complete indexable production metadata', () => {
    expect(auditIndexableHtml(validHtml(), { expectedUrl })).toEqual([])
  })

  it('reports missing and duplicate titles', () => {
    expect(auditIndexableHtml(validHtml().replace(/<title>[\s\S]*?<\/title>/, ''), { expectedUrl }))
      .toContain('expected exactly one title, received 0')
    expect(auditIndexableHtml(validHtml().replace('</head>', '<title>Zweiter Titel</title></head>'), { expectedUrl }))
      .toContain('expected exactly one title, received 2')
  })

  it('reports an empty description', () => {
    expect(auditIndexableHtml(validHtml({ description: '' }), { expectedUrl }))
      .toContain('missing or empty meta description')
  })

  it('rejects local canonical and social metadata URLs', () => {
    const local = 'http://127.0.0.1:3000/test'
    const errors = auditIndexableHtml(validHtml({ canonical: local, ogUrl: 'http://localhost:3000/test' }), { expectedUrl })
    expect(errors).toContain('canonical must use https')
    expect(errors).toContain('canonical points to a local host')
    expect(errors).toContain('og:url points to a local host')
    expect(hasLocalHost('https://api.localhost/preview.webp')).toBe(true)
  })

  it('reports missing noindex', () => {
    expect(auditNoindexHtml(validHtml())).toContain('expected robots=noindex,nofollow')
  })

  it('reports invalid JSON-LD', () => {
    expect(auditIndexableHtml(validHtml({ jsonLd: '{invalid' }), { expectedUrl }))
      .toContain('invalid JSON-LD block 1')
  })

  it('minimally validates known JSON-LD structures', () => {
    const withoutUrl = JSON.stringify({ '@context': 'https://schema.org', '@type': 'WebPage' })
    expect(auditIndexableHtml(validHtml({ jsonLd: withoutUrl }), { expectedUrl }))
      .toContain('JSON-LD WebPage in block 1 is missing url/@id')
  })

  it('reports duplicate canonicals', () => {
    const html = validHtml().replace('</head>', `<link rel="canonical" href="${expectedUrl}"></head>`)
    expect(auditIndexableHtml(html, { expectedUrl }))
      .toContain('expected exactly one canonical, received 2')
  })

  it('reports malformed OpenGraph URLs', () => {
    expect(auditIndexableHtml(validHtml({ ogUrl: 'not-a-url' }), { expectedUrl }))
      .toContain('og:url is not an absolute URL')
  })

  it('extracts escaped absolute sitemap locations', () => {
    expect(sitemapLocations('<urlset><url><loc>https://example.test/a?x=1&amp;y=2</loc></url></urlset>'))
      .toEqual(['https://example.test/a?x=1&y=2'])
  })
})

describe('SEO route inventory', () => {
  it('classifies representative dynamic, noindex, social, error and redirect routes', () => {
    expect(DYNAMIC_PUBLIC_ROUTES).toHaveLength(2)
    expect(new Set(NOINDEX_ROUTES.map(route => route.type))).toEqual(new Set(['public-noindex', 'auth', 'admin/internal']))
    expect(SOCIAL_PREVIEW_ROUTES.length).toBeGreaterThanOrEqual(3)
    expect(NOT_FOUND_ROUTES).toEqual(expect.arrayContaining([
      expect.stringMatching(/^\/gebiete\//),
      expect.stringMatching(/^\/flaechen\//)
    ]))
    expect(REDIRECT_ROUTES.length).toBeGreaterThanOrEqual(1)
  })

  it('keeps the internal API base outside public runtime config and browser requests', () => {
    const config = readFileSync(fileURLToPath(new URL('../nuxt.config.ts', import.meta.url)), 'utf8')
    const api = readFileSync(fileURLToPath(new URL('../app/composables/useApi.ts', import.meta.url)), 'utf8')
    expect(config).toContain("apiInternalBaseUrl: process.env.NUXT_API_INTERNAL_BASE_URL || ''")
    expect(config.indexOf('apiInternalBaseUrl:')).toBeLessThan(config.indexOf('public: {'))
    expect(api).toContain('? config.apiInternalBaseUrl || config.public.apiBaseUrl')
  })
})
