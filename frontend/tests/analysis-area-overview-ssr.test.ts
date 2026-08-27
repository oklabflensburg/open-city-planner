import { fileURLToPath } from 'node:url'
import { fetch, setup } from '@nuxt/test-utils/e2e'
import { describe, expect, it } from 'vitest'

type StructuredEntity = {
  '@context'?: string
  '@type'?: string
  numberOfItems?: number
  itemListElement?: Array<{
    '@type': string
    position: number
    name: string
    url: string
  }>
  mainEntity?: Array<{
    '@type': string
    name: string
    acceptedAnswer: {
      '@type': string
      text: string
    }
  }>
}

const siteUrl = 'https://stadtplaner.example'
const pageTitle = 'Gebiete in Flensburg – Standortdaten | Stadtplaner'
const questions = [
  'Wie viele Stadtteile hat Flensburg?',
  'Wie viele Quartiere hat Flensburg?',
  'Welche Stadtteile gehören zu Flensburg?',
  'Was ist der Unterschied zwischen Stadtteil und Quartier?',
  'Welche Daten zeigt der Stadtplaner für Stadtteile und Quartiere?',
  'Woher stammen die Gebietsgrenzen?',
  'Woher stammen Bevölkerungs- und Haushaltsdaten?',
  'Gibt es für jedes Quartier eigene Statistikwerte?',
  'Kann ich ein Gebiet direkt auf der Karte öffnen?'
]

process.env.OCP_FRONTEND_MODULES = 'analysis-areas'
process.env.OCP_BACKEND_MODULES = 'analysis-areas'

await setup({
  rootDir: fileURLToPath(new URL('..', import.meta.url)),
  browser: false,
  port: 3011,
  setupTimeout: 180_000,
  env: {
    NUXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:3011/api/v1',
    NUXT_PUBLIC_SITE_URL: siteUrl
  },
  nuxtConfig: {
    runtimeConfig: {
      public: {
        apiBaseUrl: 'http://127.0.0.1:3011/api/v1',
        siteUrl
      }
    },
    nitro: {
      handlers: [{
        route: '/api/v1/analysis-areas',
        handler: fileURLToPath(new URL('./fixtures/analysis-areas.get.ts', import.meta.url))
      }]
    }
  }
})

function renderedText(html: string) {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\b[^>]*>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\b[^>]*>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&amp;', '&')
    .replace(/\s+/g, ' ')
    .trim()
}

function structuredData(html: string): StructuredEntity[] {
  return [...html.matchAll(/<script[^>]+type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)]
    .flatMap((match) => {
      const parsed = JSON.parse(match[1]!) as StructuredEntity | StructuredEntity[]
      return Array.isArray(parsed) ? parsed : [parsed]
    })
}

function tags(html: string, name: 'meta' | 'link') {
  return [...html.matchAll(new RegExp(`<${name}\\b[^>]*>`, 'g'))].map(match => match[0])
}

function attributes(tag: string) {
  return Object.fromEntries(
    [...tag.matchAll(/([:\w-]+)="([^"]*)"/g)].map(match => [match[1], match[2]])
  )
}

function expectMetadata(html: string, robots: 'index,follow' | 'noindex,nofollow') {
  const meta = tags(html, 'meta').map(attributes)
  const links = tags(html, 'link').map(attributes)

  expect(html).toContain(`<title>${pageTitle}</title>`)
  expect(meta.find(item => item.name === 'description')?.content).toBeTruthy()
  expect(meta.find(item => item.property === 'og:title')?.content).toBe(pageTitle)
  expect(meta.find(item => item.property === 'og:description')?.content).toBeTruthy()
  expect(meta.find(item => item.property === 'og:url')?.content).toBe(`${siteUrl}/gebiete`)
  expect(meta.find(item => item.name === 'robots')?.content).toBe(robots)
  expect(links.find(item => item.rel === 'canonical')?.href).toBe(`${siteUrl}/gebiete`)
}

describe('area overview SSR integration', () => {
  it('renders deterministic counts, FAQ, links and parseable structured data', async () => {
    const response = await fetch('/gebiete')
    expect(response.status).toBe(200)
    const html = await response.text()
    const text = renderedText(html)

    expect(text).toContain('2 Stadtteile')
    expect(text).toContain('3 Quartiere')
    expect(text).toContain('6 veröffentlichte Gebiete')
    expect(text).toMatch(/Gebiete gesamt 6/)
    for (const question of questions) expect(text).toContain(question)

    expect(html).toContain('href="/gebiete/altstadt"')
    expect(html).toContain('href="/gebiete/neustadt"')
    expect(html).toContain('href="/dokumentation/methodik"')
    expect(html).toMatch(/href="\/karte"[^>]*>GIS-Karte öffnen<\/a>/)
    expectMetadata(html, 'index,follow')

    const entities = structuredData(html)
    expect(entities).toHaveLength(4)
    expect(entities.every(entity => entity['@context'] === 'https://schema.org')).toBe(true)
    expect(entities.map(entity => entity['@type'])).toEqual([
      'BreadcrumbList',
      'CollectionPage',
      'ItemList',
      'FAQPage'
    ])

    const itemList = entities.find(entity => entity['@type'] === 'ItemList')
    expect(itemList).toMatchObject({
      numberOfItems: 2,
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'Altstadt',
          url: `${siteUrl}/gebiete/altstadt`
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'Neustadt',
          url: `${siteUrl}/gebiete/neustadt`
        }
      ]
    })

    const faqPage = entities.find(entity => entity['@type'] === 'FAQPage')
    expect(faqPage?.mainEntity?.map(entity => entity.name)).toEqual(questions)
    for (const entity of faqPage?.mainEntity || []) {
      expect(entity['@type']).toBe('Question')
      expect(entity.acceptedAnswer['@type']).toBe('Answer')
      expect(text).toContain(entity.acceptedAnswer.text)
    }
    expect(faqPage?.mainEntity?.[0]?.acceptedAnswer.text).toContain('2 Stadtteile')
    expect(faqPage?.mainEntity?.[1]?.acceptedAnswer.text).toContain('3 veröffentlichte Quartiere')
    expect(faqPage?.mainEntity?.[2]?.acceptedAnswer.text).toContain('Altstadt, Neustadt')
  })

  it('renders the empty state without false zero-count claims or an ItemList', async () => {
    const response = await fetch('/gebiete', {
      headers: { cookie: 'analysis-area-fixture=empty' }
    })
    expect(response.status).toBe(200)
    const html = await response.text()
    const text = renderedText(html)
    const entities = structuredData(html)

    expect(text).toContain('Derzeit sind keine auswertbaren Gebiete veröffentlicht.')
    expect(text).not.toContain('Wie viele Stadtteile hat Flensburg?')
    expect(text).not.toContain('Wie viele Quartiere hat Flensburg?')
    expect(text).not.toMatch(/0 (?:Stadtteile|Quartiere|veröffentlichte Gebiete)/)
    expect(entities.some(entity => entity['@type'] === 'ItemList')).toBe(false)
    expect(entities.find(entity => entity['@type'] === 'FAQPage')?.mainEntity).toHaveLength(6)
  })

  it('keeps metadata canonical while social preview is noindex', async () => {
    const response = await fetch('/gebiete?social-preview=1')
    expect(response.status).toBe(200)
    const html = await response.text()

    expectMetadata(html, 'noindex,nofollow')
    expect(html).not.toContain(`${siteUrl}/gebiete?social-preview=1`)
  })
})
