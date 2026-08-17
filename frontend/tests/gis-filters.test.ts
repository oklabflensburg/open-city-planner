import { describe, expect, it } from 'vitest'
import { effectiveGisFilters, gisFilterQuery, gisFiltersFromQuery, gisFilterStateKey, gisFilterUrlQuery } from '~/utils/gisFilters'

const selection = {
  sizes: ['S', 'M'] as const,
  floors: ['EG', 'OG'] as const,
  categories: ['fashion', 'gastronomy'] as const,
  statuses: ['VACANT'] as const,
  businessStructures: [],
  sources: ['STADTPLANNER', 'OSM'] as const
}

describe('GIS filter serialization', () => {
  it('serializes every group consistently and restores it from the URL', () => {
    const query = gisFilterUrlQuery({
      sizes: [...selection.sizes], floors: [...selection.floors], categories: [...selection.categories],
      statuses: [...selection.statuses], businessStructures: [], sources: [...selection.sources]
    })
    const restored = gisFiltersFromQuery(Object.fromEntries(query))

    expect(query.toString()).toBe('area_sizes=S%2CM&floors=EG%2COG&categories=fashion%2Cgastronomy&occupancy_statuses=VACANT')
    expect(restored).toEqual({
      sizes: ['S', 'M'], floors: ['EG', 'OG'], categories: ['fashion', 'gastronomy'],
      statuses: ['VACANT'], businessStructures: [], sources: ['STADTPLANNER', 'OSM']
    })
    expect(gisFilterStateKey(restored)).toBe(query.toString())
  })

  it('treats no values and all values as an unrestricted API filter', () => {
    const allSizes = { sizes: ['S', 'M', 'L', 'XL'] as Array<'S' | 'M' | 'L' | 'XL'>, floors: [], categories: [], statuses: [], businessStructures: [], sources: ['STADTPLANNER', 'OSM'] as Array<'STADTPLANNER' | 'OSM'> }
    expect(gisFilterQuery(allSizes).toString()).toBe('')
    expect(effectiveGisFilters(allSizes).sizes).toEqual([])
  })

  it('ignores invalid URL values instead of leaking them into API requests', () => {
    expect(gisFiltersFromQuery({ area_sizes: 'S,XXL', floors: 'basement' })).toEqual({
      sizes: ['S'], floors: [], categories: [], statuses: [], businessStructures: [], sources: ['STADTPLANNER', 'OSM']
    })
  })

  it('represents an explicitly empty data-source selection without confusing it with the default', () => {
    const filters = { sizes: [], floors: [], categories: [], statuses: [], businessStructures: [], sources: [] }
    expect(gisFilterQuery(filters).get('sources')).toBe('NONE')
    expect(gisFiltersFromQuery({ sources: 'NONE' }).sources).toEqual([])
    expect(gisFiltersFromQuery({}).sources).toEqual(['STADTPLANNER', 'OSM'])
  })
})
