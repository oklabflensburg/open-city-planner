import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useComparisonStore } from '~/stores/comparison'

const filterState = {
  sizes: ['M'], floors: ['EG'], categories: ['gastronomy'], statuses: ['VACANT'],
  businessStructures: ['INDEPENDENT'], sources: ['STADTPLANNER']
}

function response(slug: string) {
  return {
    areas: [{ id: `${slug}-id`, slug, name: slug, area_type: 'DISTRICT', parent_name: 'Flensburg', area_m2: 1_000_000, metrics: {
      polygon_count: 3, occupied_count: 2, vacant_count: 1, chain_count: 0, independent_count: 3,
      total_area_m2: 300, average_area_m2: 100, median_area_m2: 90, vacancy_rate: 33.3,
      chain_store_rate: 0, known_occupancy_count: 3, known_business_structure_count: 3,
      data_updated_at: null, locations_per_km2: 3, retail_area_m2_per_km2: 300
    }}], benchmark: null, ignored_slugs: [], calculation: 'CALCULATED', source: 'Erfasste Stadtplaner-Flächen'
  }
}

describe('comparison store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('useFilterStore', () => ({ filterState }))
  })

  it('sends all areas and the same active filters in one compare request', async () => {
    const request = vi.fn().mockResolvedValue(response('innenstadt'))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useComparisonStore()

    await store.compare(['innenstadt', 'neustadt'], true)

    expect(request).toHaveBeenCalledTimes(1)
    const [path, options] = request.mock.calls[0]
    expect(path).toBe('/analytics/compare')
    expect(JSON.parse(options.body)).toEqual({
      area_slugs: ['innenstadt', 'neustadt'], include_municipality_benchmark: true,
      filters: {
        categories: ['gastronomy'], floors: ['EG'], area_sizes: ['M'],
        occupancy_statuses: ['VACANT'], business_structures: ['INDEPENDENT'], sources: ['STADTPLANNER']
      }
    })
  })

  it('aborts an older request and only applies the newest response', async () => {
    let firstSignal: AbortSignal | undefined
    const request = vi.fn()
      .mockImplementationOnce((_path, options) => {
        firstSignal = options.signal
        return new Promise(resolve => setTimeout(() => resolve(response('innenstadt')), 20))
      })
      .mockResolvedValueOnce(response('neustadt'))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useComparisonStore()

    const first = store.compare(['innenstadt'], false)
    await store.compare(['neustadt'], false)
    await first

    expect(firstSignal?.aborted).toBe(true)
    expect(store.result?.areas[0]?.slug).toBe('neustadt')
    expect(store.loading).toBe(false)
  })
})
