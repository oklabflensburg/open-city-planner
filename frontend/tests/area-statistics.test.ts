import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')
const moduleFile = (path: string) => readFileSync(fileURLToPath(new URL(`../frontend-modules/analysis-areas/layer/app/${path}`, import.meta.url)), 'utf8')

describe('municipal area statistics', () => {
  it('loads statistics and a real time series during SSR', () => {
    const page = moduleFile('pages/gebiete/[slug].vue')
    const api = appFile('composables/useAnalysisAreaApi.ts')
    expect(page).toContain('api.statisticsBySlug(slug)')
    expect(page).toContain("api.statisticSeriesBySlug(slug, 'population')")
    expect(page).toContain('<AreaStatistics')
    expect(api).toContain('/statistics/${encodeURIComponent(metric)}')
  })

  it('renders source, period, license and accessible HTML values', () => {
    const component = appFile('components/analysis/AreaStatistics.vue')
    expect(component).toContain('Kommunale Statistik')
    expect(component).toContain('Datenquelle:')
    expect(component).toContain('Datenstand:')
    expect(component).toContain('Lizenz:')
    expect(component).toContain('<table')
    expect(component).toContain('<th v-for="point in recentSeries"')
  })

  it('labels parent district values on quarter pages', () => {
    const component = appFile('components/analysis/AreaStatistics.vue')
    expect(component).toContain('statistics.inherited_from_parent')
    expect(component).toContain('keine eigenen Zahlenspiegel-Werte')
    expect(component).toContain('gesamten Stadtteil')
  })

  it('shows only compact statistics in the responsive GIS selection card', () => {
    const card = appFile('components/analysis/AnalysisAreaCard.vue')
    const store = appFile('stores/analysisAreas.ts')
    expect(card).toContain("['population', 'households']")
    expect(card).toContain('Kommunale Statistik')
    expect(store).toContain('statistics: null as AreaStatistics | null')
    expect(store).toContain('/statistics`)')
  })

  it('documents the source mapping and does not call Superset from the browser', () => {
    const component = appFile('components/analysis/AreaStatistics.vue')
    const api = appFile('composables/useAnalysisAreaApi.ts')
    expect(component).toContain('OpenStreetMap-Grenzen')
    expect(component).toContain('geometrisch exakte Übereinstimmung')
    expect(api).not.toContain('superset.flensburg.de')
  })
})
