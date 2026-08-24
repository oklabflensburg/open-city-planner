import { fileURLToPath } from 'node:url'
import { fetch, setup } from '@nuxt/test-utils/e2e'
import { describe, expect, it } from 'vitest'

const siteUrl = 'https://stadtplaner.example'

await setup({
  rootDir: fileURLToPath(new URL('..', import.meta.url)),
  browser: false,
  port: 3012,
  setupTimeout: 180_000,
  env: {
    NUXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:3012/api/v1',
    NUXT_PUBLIC_SITE_URL: siteUrl
  },
  nuxtConfig: {
    runtimeConfig: {
      public: {
        apiBaseUrl: 'http://127.0.0.1:3012/api/v1',
        siteUrl
      }
    },
    nitro: {
      handlers: [{
        route: '/api/v1/**',
        handler: fileURLToPath(new URL('./fixtures/seo-api.get.ts', import.meta.url))
      }]
    }
  }
})

function tags(html: string, name: 'meta' | 'link') {
  return [...html.matchAll(new RegExp(`<${name}\\b[^>]*>`, 'g'))].map(match => match[0])
}

function attributes(tag: string) {
  return Object.fromEntries(
    [...tag.matchAll(/([:\w-]+)="([^"]*)"/g)].map(match => [match[1], match[2]])
  )
}

function expectCanonical(html: string, path: string, robots: 'index,follow' | 'noindex,nofollow') {
  const meta = tags(html, 'meta').map(attributes)
  const links = tags(html, 'link').map(attributes)
  expect(links.find(item => item.rel === 'canonical')?.href).toBe(`${siteUrl}${path}`)
  expect(meta.find(item => item.property === 'og:url')?.content).toBe(`${siteUrl}${path}`)
  expect(meta.find(item => item.name === 'robots')?.content).toBe(robots)
}

describe('SEO routes over Nuxt HTTP', () => {
  it('serves complete crawler guidance without excluding public pages', async () => {
    const response = await fetch('/robots.txt')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('text/plain; charset=utf-8')
    const body = await response.text()

    for (const path of [
      '/login', '/registrieren', '/profil', '/meine-flaechen', '/flaechen/neu',
      '/passwort-', '/email-bestaetigen', '/email-abmelden', '/auth/', '/admin/', '/verwaltung/'
    ]) {
      expect(body).toContain(`Disallow: ${path}`)
    }
    expect(body).toContain(`Sitemap: ${siteUrl}/sitemap.xml`)
    const disallowed = body.match(/^Disallow: (.+)$/gm)?.map(line => line.slice('Disallow: '.length)) || []
    for (const publicPath of ['/', '/gebiete/altstadt', '/flaechen/test-flaeche', '/vergleich', '/dokumentation/faq', '/open-data', '/kontakt', '/ueber-das-projekt']) {
      expect(disallowed.some(rule => publicPath.startsWith(rule))).toBe(false)
    }
  })

  it('serves a deterministic, duplicate-free public sitemap with lastmod values', async () => {
    const response = await fetch('/sitemap.xml')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('application/xml; charset=utf-8')
    expect(response.headers.get('cache-control')).toBe('no-cache, must-revalidate')
    const xml = await response.text()

    expect(xml).toMatch(/^<\?xml version="1\.0" encoding="UTF-8"\?>\n<urlset xmlns="http:\/\/www\.sitemaps\.org\/schemas\/sitemap\/0\.9">/)
    expect(xml).toMatch(/<\/urlset>\n$/)
    const locations = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1])
    expect(locations.length).toBeGreaterThan(6)
    expect(new Set(locations).size).toBe(locations.length)
    for (const path of ['/', '/gebiete', '/vergleich', '/open-data', '/kontakt', '/dokumentation', '/flaechen/test-flaeche', '/gebiete/altstadt']) {
      expect(locations).toContain(`${siteUrl}${path}`)
    }
    expect(xml).toContain('<lastmod>2026-08-24T10:00:00Z</lastmod>')
    expect(xml).toContain('<lastmod>2026-08-24T09:00:00Z</lastmod>')
    expect(locations.every((location) => {
      const path = new URL(location).pathname
      return ![
        '/login', '/registrieren', '/profil', '/admin', '/verwaltung', '/meine-flaechen',
        '/flaechen/neu', '/email-bestaetigen', '/email-abmelden'
      ].some(
        excluded => path === excluded || path.startsWith(`${excluded}/`)
      ) && !path.startsWith('/passwort-') && !path.startsWith('/auth/')
    })).toBe(true)
    expect(locations.join('\n')).not.toMatch(/(?:localhost|127\.0\.0\.1|\?)/)
    expect((xml.match(/<url>/g) || [])).toHaveLength(locations.length)
    expect((xml.match(/<\/url>/g) || [])).toHaveLength(locations.length)
  })

  it.each([
    ['/?social-preview=1&polygon=fixture', '/', 'noindex,nofollow'],
    ['/vergleich?gebiete=altstadt&benchmark=0', '/vergleich', 'index,follow'],
    ['/gebiete/altstadt?social-preview=1&map=0', '/gebiete/altstadt', 'noindex,nofollow'],
    ['/flaechen/test-flaeche?social-preview=1&map=0', '/flaechen/test-flaeche', 'noindex,nofollow']
  ] as const)('keeps %s canonical at %s', async (requestPath, canonicalPath, robots) => {
    const response = await fetch(requestPath)
    expect(response.status).toBe(200)
    const html = await response.text()
    expectCanonical(html, canonicalPath, robots)
    expect(html).not.toContain(`${siteUrl}${requestPath}`)
  })

  it.each(['/gebiete/does-not-exist', '/flaechen/does-not-exist'])(
    'renders %s as a noindex 404',
    async (path) => {
      const response = await fetch(path, { redirect: 'manual', headers: { accept: 'text/html' } })
      expect(response.status).toBe(404)
      const html = await response.text()
      const meta = tags(html, 'meta').map(attributes)
      expect(meta.find(item => item.name === 'robots')?.content).toBe('noindex,nofollow')
      expect(html).toContain('Seite nicht gefunden')
    }
  )
})
