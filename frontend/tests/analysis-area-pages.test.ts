import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { mapHostSource } from './map-host-source'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')
const moduleFile = (path: string) => readFileSync(fileURLToPath(new URL(`../frontend-modules/analysis-areas/layer/app/${path}`, import.meta.url)), 'utf8')

describe('public analysis area pages', () => {
  it('loads one shared municipality, district and quarter template during SSR', () => {
    const page = moduleFile('pages/gebiete/[slug].vue')
    expect(page).toContain('await useAsyncData')
    expect(page).toContain('api.bySlug')
    expect(page).toContain("MUNICIPALITY: 'Gemeinde'")
    expect(page).toContain("DISTRICT: 'Stadtteil'")
    expect(page).toContain("QUARTER: 'Quartier'")
    expect(page).toContain("statusCode: statusCode === 404 ? 404 : 500")
  })

  it('renders real metrics, comparison, hierarchy and missing values as a dash', () => {
    const page = moduleFile('pages/gebiete/[slug].vue')
    for (const content of ['Kennzahlen', 'Leerstandsquote', 'Filialisierungsgrad', 'Branchenverteilung', 'Orte und Einrichtungen im Gebiet', 'Untergeordnete Gebiete', 'Flächen im Gebiet']) {
      expect(page).toContain(content)
    }
    expect(page).toContain("value == null ? '—'")
    expect(page).toContain('comparison.differences')
    expect(page).toContain('area.municipality')
  })

  it('provides canonical, social and structured SEO data', () => {
    const seo = appFile('composables/useAnalysisAreaSeo.ts')
    expect(seo).toContain("robots: 'index,follow'")
    expect(seo).toContain("rel: 'canonical'")
    expect(seo).toContain("'@type': 'AdministrativeArea'")
    expect(seo).toContain('buildBreadcrumbStructuredData')
    expect(seo).toContain('ogTitle')
    expect(seo).toContain('twitterCard')
    expect(seo).toContain('sameAs')
    expect(seo).toContain('external_links.wikidata?.url')
  })

  it('renders only persisted external sources with safe new-tab semantics', () => {
    const page = moduleFile('pages/gebiete/[slug].vue')
    const links = appFile('components/analysis/AreaExternalLinks.vue')
    const sourceLink = appFile('components/analysis/ExternalSourceLink.vue')
    expect(page).toContain('Externe Quellen')
    expect(page).toContain('area.external_links.wikipedia')
    expect(page).toContain('variant="card"')
    expect(links).toContain('Enzyklopädischer Artikel')
    expect(links).toContain('Strukturierte offene Wissensdaten')
    expect(sourceLink).toContain('target="_blank"')
    expect(sourceLink).toContain('rel="noopener noreferrer"')
    expect(sourceLink).toContain('break-words')
  })

  it('links area pages and the GIS selection in both directions', () => {
    expect(moduleFile('pages/gebiete/[slug].vue')).toContain("path: '/karte', query: { gebiet: area.slug }")
    expect(appFile('components/analysis/AnalysisAreaCard.vue')).toContain('`/gebiete/${area.slug}`')
    const map = mapHostSource()
    expect(map).toContain('route.query.area')
    expect(map).toContain('route.query.gebiet')
    expect(map).toContain('selectRequestedArea')
  })

  it('uses central industry colors and accessible links for localized places', () => {
    const page = moduleFile('pages/gebiete/[slug].vue')
    expect(page).toContain('getIndustryColor(item.category)')
    expect(page).toContain('getPoiCategoryLabel(item.category)')
    expect(page).toContain('areaPoiMapLink(area.slug, item.category)')
    expect(page).toContain('im Gebiet ${area.name} auf der Karte anzeigen')
    expect(page).not.toContain('{{ item.category }}')
  })
})
