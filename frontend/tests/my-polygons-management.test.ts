import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { UserPolygon } from '../app/types/geo'
import { getIndustryLabel } from '../app/utils/industries'
import { filterAndSortPolygons, normalizePolygonSearchValue } from '../app/utils/polygonManagement'

const geometry: UserPolygon['geometry'] = {
  type: 'Polygon',
  coordinates: [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]]
}

function polygon(
  id: string,
  name: string,
  category: string,
  createdAt: string,
  updatedAt: string,
  properties: Record<string, unknown> = {}
): UserPolygon {
  return {
    id,
    slug: name.toLocaleLowerCase('de-DE').replace(/\s+/g, '-'),
    name,
    category,
    geometry,
    properties,
    created_at: createdAt,
    updated_at: updatedAt
  }
}

const polygons = [
  polygon('1', 'Zentraler Markt', 'food', '2026-01-03T10:00:00Z', '2026-03-01T10:00:00Z', { address: 'Nordermarkt 1' }),
  polygon('2', 'Alte Börse', 'gastronomy', '2026-02-03T10:00:00Z', '2026-04-01T10:00:00Z'),
  polygon('3', 'Modehaus', 'fashion', '2026-03-03T10:00:00Z', '2026-02-01T10:00:00Z')
]

describe('Meine-Flächen-Verwaltungslogik', () => {
  it('uses the canonical German category labels', () => {
    expect(getIndustryLabel('gastronomy')).toBe('Gastronomie')
    expect(getIndustryLabel('services')).toBe('Einzelhandelsnahe Dienstleister')
  })

  it('normalizes case and German umlauts', () => {
    expect(normalizePolygonSearchValue('  ALTE BÖRSE  ')).toBe('alte boerse')
  })

  it('searches names, German labels and delivered property values without case sensitivity', () => {
    expect(filterAndSortPolygons(polygons, 'markt', '', 'updated-desc').map(item => item.id)).toEqual(['1'])
    expect(filterAndSortPolygons(polygons, 'GASTRONOMIE', '', 'updated-desc').map(item => item.id)).toEqual(['2'])
    expect(filterAndSortPolygons(polygons, 'Nordermarkt', '', 'updated-desc').map(item => item.id)).toEqual(['1'])
    expect(filterAndSortPolygons(polygons, '', '', 'updated-desc')).toHaveLength(3)
  })

  it('combines exact category filtering with search', () => {
    expect(filterAndSortPolygons(polygons, '', 'fashion', 'updated-desc').map(item => item.id)).toEqual(['3'])
    expect(filterAndSortPolygons(polygons, 'Börse', 'food', 'updated-desc')).toEqual([])
  })

  it('sorts by German name and latest update without mutating the source list', () => {
    expect(filterAndSortPolygons(polygons, '', '', 'name-asc').map(item => item.name)).toEqual([
      'Alte Börse', 'Modehaus', 'Zentraler Markt'
    ])
    expect(filterAndSortPolygons(polygons, '', '', 'updated-desc').map(item => item.id)).toEqual(['2', '1', '3'])
    expect(polygons.map(item => item.id)).toEqual(['1', '2', '3'])
  })
})

describe('Meine-Flächen-Seitenzustände', () => {
  const page = readFileSync(fileURLToPath(new URL('../app/pages/meine-flaechen.vue', import.meta.url)), 'utf8')

  it('keeps auth and the distinct loading, error, empty and no-result states', () => {
    expect(page).toContain("definePageMeta({ middleware: 'auth' })")
    expect(page).toContain('Flächen werden geladen')
    expect(page).toContain('Flächen konnten nicht geladen werden.')
    expect(page).toContain('Noch keine eigenen Flächen')
    expect(page).toContain('Keine Flächen gefunden')
  })

  it('provides query-backed controls, live results and separate mobile and desktop views', () => {
    expect(page).toContain('route.query.q')
    expect(page).toContain('route.query.category')
    expect(page).toContain('route.query.sort')
    expect(page).toContain('aria-live="polite"')
    expect(page).toContain('aria-label="Suche zurücksetzen"')
    expect(page).toContain('md:hidden')
    expect(page).toContain('hidden overflow-x-auto md:block')
    expect(page).toContain('<PolygonCategoryBadge')
  })
})
