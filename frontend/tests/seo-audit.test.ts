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
  REDIRECT_ROUTES
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
  return `<!doctype html><html><head><title>${title}</title><meta name="description" content="${description}"><meta name="robots" content="${robots}"><meta name="theme-color" content="#154d73"><link rel="canonical" href="${canonical}"><link rel="icon" href="/favicon.ico"><link rel="icon" type="image/svg+xml" href="/branding/ok-lab-flensburg.svg"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96x96.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest"><meta property="og:title" content="${title}"><meta property="og:description" content="${description}"><meta property="og:url" content="${ogUrl}"><meta property="og:type" content="website"><meta property="og:site_name" content="OK Lab Flensburg"><meta property="og:locale" content="de_DE"><meta property="og:image" content="https://stadtplaner.example.test/branding/stadtplaner-social-card.png"><meta property="og:image:alt" content="Stadtplaner des OK Lab Flensburg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:site" content="@oklabflensburg"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${title}"><meta name="twitter:description" content="${description}"><meta name="twitter:image" content="https://stadtplaner.example.test/branding/stadtplaner-social-card.png"><meta name="twitter:image:alt" content="Stadtplaner des OK Lab Flensburg"><script type="application/ld+json">${jsonLd}</script></head><body><h1>Testseite</h1></body></html>`
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

  it('supports public noindex pages that allow link following', () => {
    expect(auditNoindexHtml(validHtml().replace('index,follow', 'noindex,follow'), {
      expectedRobots: 'noindex,follow'
    })).toEqual([])
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

  it('reports missing social dimensions and global technical metadata', () => {
    const html = validHtml()
      .replace('<meta property="og:image:width" content="1200">', '')
      .replace('<meta name="theme-color" content="#154d73">', '')
      .replace('<link rel="manifest" href="/site.webmanifest">', '')
    const errors = auditIndexableHtml(html, { expectedUrl })

    expect(errors).toContain('expected og:image:width=1200')
    expect(errors).toContain('expected theme-color=#154d73')
    expect(errors).toContain('missing global manifest /site.webmanifest')
  })

  it('extracts escaped absolute sitemap locations', () => {
    expect(sitemapLocations('<urlset><url><loc>https://example.test/a?x=1&amp;y=2</loc></url></urlset>'))
      .toEqual(['https://example.test/a?x=1&y=2'])
  })
})

describe('SEO route inventory', () => {
  it('classifies representative dynamic, noindex, error and redirect routes', () => {
    expect(DYNAMIC_PUBLIC_ROUTES).toHaveLength(1)
    expect(new Set(NOINDEX_ROUTES.map(route => route.type))).toEqual(new Set(['public-noindex', 'auth']))
    expect(NOT_FOUND_ROUTES).toEqual(expect.arrayContaining([
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
