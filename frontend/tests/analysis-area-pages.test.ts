import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('public analysis area pages', () => {
  it('loads one shared municipality, district and quarter template during SSR', () => {
    const page = appFile('pages/gebiete/[slug].vue')
    expect(page).toContain('await useAsyncData')
    expect(page).toContain('api.bySlug')
    expect(page).toContain("MUNICIPALITY: 'Gemeinde'")
    expect(page).toContain("DISTRICT: 'Stadtteil'")
    expect(page).toContain("QUARTER: 'Quartier'")
    expect(page).toContain("statusCode: statusCode === 404 ? 404 : 500")
  })

  it('renders real metrics, comparison, hierarchy and missing values as a dash', () => {
    const page = appFile('pages/gebiete/[slug].vue')
    for (const content of ['Kennzahlen', 'Leerstandsquote', 'Filialisierungsgrad', 'Branchenverteilung', 'OpenStreetMap im Gebiet', 'Untergeordnete Gebiete', 'Flächen im Gebiet']) {
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
  })

  it('links area pages and the GIS selection in both directions', () => {
    expect(appFile('pages/gebiete/[slug].vue')).toContain('`/?area=${area.slug}`')
    expect(appFile('components/analysis/AnalysisAreaCard.vue')).toContain('`/gebiete/${area.slug}`')
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('route.query.area')
    expect(map).toContain('selectRequestedArea')
  })
})
