import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { AnalysisArea, AnalysisAreaType } from '~/types/analysisArea'
import { countAnalysisAreasByType, sortAnalysisAreasByName } from '../frontend-modules/analysis-areas/layer/app/utils/analysisAreaOverview'

const overviewPage = () => readFileSync(
  fileURLToPath(new URL('../frontend-modules/analysis-areas/layer/app/pages/gebiete/index.vue', import.meta.url)),
  'utf8'
)

function area(
  id: string,
  name: string,
  areaType: AnalysisAreaType
): AnalysisArea {
  return {
    id,
    slug: name.toLocaleLowerCase('de').replaceAll(' ', '-'),
    name,
    area_type: areaType,
    parent_id: null,
    parent_name: null,
    parent_slug: null,
    area_m2: 1,
    source: 'OSM',
    source_osm_type: 'relation',
    source_osm_id: 1,
    source_admin_level: null,
    source_place: null,
    source_updated_at: null,
    updated_at: '2026-01-01T00:00:00Z',
    child_count: 0,
    external_links: { wikidata: null, wikipedia: null }
  }
}

describe('area overview', () => {
  const areas = [
    area('1', 'Flensburg', 'MUNICIPALITY'),
    area('2', 'Neustadt', 'DISTRICT'),
    area('3', 'Altstadt', 'DISTRICT'),
    area('4', 'Nordertor', 'QUARTER'),
    area('5', 'Duburg', 'QUARTER'),
    area('6', 'Hafen', 'QUARTER')
  ]

  it('derives municipality, district, quarter and total counts from the dataset', () => {
    expect(countAnalysisAreasByType(areas, 'MUNICIPALITY')).toBe(1)
    expect(countAnalysisAreasByType(areas, 'DISTRICT')).toBe(2)
    expect(countAnalysisAreasByType(areas, 'QUARTER')).toBe(3)
    expect(areas).toHaveLength(6)
  })

  it('sorts linked districts by their German display names', () => {
    expect(sortAnalysisAreasByName(areas.filter(item => item.area_type === 'DISTRICT')))
      .toMatchObject([{ name: 'Altstadt' }, { name: 'Neustadt' }])
  })

  it('keeps FAQ counts dynamic and all structured data SSR-bound', () => {
    const page = overviewPage()

    expect(page).toContain('const districtCount = computed(')
    expect(page).toContain('const quarterCount = computed(')
    expect(page).toContain('const totalAreaCount = computed(')
    expect(page).toContain('${districtCount.value}')
    expect(page).toContain('${quarterCount.value}')
    expect(page).not.toMatch(/(?:sind|aktuell|weist) 13 Stadtteile/)
    expect(page).toContain('Wie viele Stadtteile hat Flensburg?')
    expect(page).toContain('Wie viele Quartiere hat Flensburg?')
    expect(page).toContain('buildBreadcrumbStructuredData')
    expect(page).toContain('buildCollectionPageStructuredData')
    expect(page).toContain('buildItemListStructuredData')
    expect(page).toContain('buildFaqStructuredData')
    expect(page).toContain("robots: socialPreview.value ? 'noindex,nofollow'")
    expect(page.match(/areaApi\.list\(\)/g)).toHaveLength(1)
  })
})
