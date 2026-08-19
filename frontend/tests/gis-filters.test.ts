import { describe, expect, it } from 'vitest'
import { effectiveGisFilters, gisFilterQuery, gisFiltersFromQuery, gisFilterStateKey, gisFilterUrlQuery } from '~/utils/gisFilters'

const selection = {
  sizes: ['S', 'M'] as const,
  floors: ['EG', 'OG'] as const,
  categories: ['fashion', 'gastronomy'] as const,
  statuses: ['VACANT'] as const,
  businessStructures: ['CHAIN'] as const,
  sources: ['STADTPLANNER', 'OSM'] as const
}

describe('GIS filter serialization', () => {
  it('serializes every group consistently and restores it from the URL', () => {
    const query = gisFilterUrlQuery({
      sizes: [...selection.sizes], floors: [...selection.floors], categories: [...selection.categories],
      statuses: [...selection.statuses], businessStructures: [...selection.businessStructures], sources: [...selection.sources]
    })
    const restored = gisFiltersFromQuery(Object.fromEntries(query))

    expect(query.toString()).toBe('area_sizes=S%2CM&floors=EG%2COG&categories=fashion%2Cgastronomy&occupancy_statuses=VACANT&business_structures=CHAIN')
    expect(restored).toEqual({
      sizes: ['S', 'M'], floors: ['EG', 'OG'], categories: ['fashion', 'gastronomy'],
      statuses: ['VACANT'], businessStructures: ['CHAIN'], sources: ['STADTPLANNER', 'OSM']
    })
    expect(gisFilterStateKey(restored)).toBe(query.toString())
  })

  it('treats all values as unrestricted and no values as explicitly empty', () => {
    const allSizes = { sizes: ['S', 'M', 'L', 'XL'] as Array<'S' | 'M' | 'L' | 'XL'>, floors: [], categories: [], statuses: [], businessStructures: [], sources: ['STADTPLANNER', 'OSM'] as Array<'STADTPLANNER' | 'OSM'> }
    expect(gisFilterQuery(allSizes).get('area_sizes')).toBeNull()
    expect(gisFilterQuery(allSizes).get('floors')).toBe('NONE')
    expect(effectiveGisFilters(allSizes).sizes).toEqual([])
  })

  it('normalisiert ungültige oder leere Fachfacetten auf uneingeschränkt', () => {
    expect(gisFiltersFromQuery({ area_sizes: 'S,XXL', floors: 'basement' })).toEqual({
      sizes: ['S'], floors: ['UG', 'EG', 'OG'], categories: expect.any(Array), statuses: expect.any(Array), businessStructures: expect.any(Array), sources: ['STADTPLANNER', 'OSM']
    })
    expect(gisFiltersFromQuery({ floors: 'NONE' }).floors).toEqual(['UG', 'EG', 'OG'])
  })

  it('represents an explicitly empty data-source selection without confusing it with the default', () => {
    const filters = gisFiltersFromQuery({ sources: 'NONE' })
    expect(gisFilterQuery(filters).get('categories')).toBeNull()
    expect(gisFilterQuery(filters).get('sources')).toBe('NONE')
    expect(gisFiltersFromQuery({ sources: 'NONE' }).sources).toEqual([])
    expect(gisFiltersFromQuery({}).sources).toEqual(['STADTPLANNER', 'OSM'])
  })
})
