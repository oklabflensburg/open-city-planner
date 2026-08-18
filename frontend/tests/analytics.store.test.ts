import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAnalyticsStore } from '~/stores/analytics'

const response = {
  fast_facts: {
    shops: 2,
    polygon_count: 2,
    vacancy_rate: null,
    chain_store_rate: null,
    centrality_index: null,
    purchasing_power_index: null,
    total_area_m2: 240,
    average_area_m2: 120,
    calculated_vacancy_rate: null,
    calculated_chain_store_rate: null,
    known_occupancy_count: 0,
    known_business_structure_count: 0,
    reference_date: null,
    source: null,
    updated_at: '2026-08-13T08:30:00Z'
  },
  industry_distribution: [{ category: 'fashion', count: 2 }],
  category_counts: [{ category: 'fashion', count: 2 }],
  prime_rents: { unit: 'EUR_PER_SQM', period: null, rows: [] }
}

describe('analytics store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('useFilterStore', () => ({
      activeCategories: ['fashion'],
      selectedFloors: ['EG'],
      selectedSizes: ['M'],
      occupancyStatuses: ['OCCUPIED', 'VACANT', 'UNKNOWN'],
      businessStructures: ['CHAIN', 'INDEPENDENT', 'UNKNOWN'],
      selectedSources: ['STADTPLANNER', 'OSM'],
      filterState: {
        sizes: ['M'], floors: ['EG'], categories: ['fashion'], statuses: ['OCCUPIED', 'VACANT', 'UNKNOWN'], businessStructures: ['CHAIN', 'INDEPENDENT', 'UNKNOWN'], sources: ['STADTPLANNER', 'OSM']
      }
    }))
  })

  it('loads real API data with the active filter query', async () => {
    const request = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAnalyticsStore()

    await store.load()

    expect(request).toHaveBeenCalledWith('/analytics/overview?area_sizes=M&floors=EG&categories=fashion', { signal: expect.any(AbortSignal) })
    expect(store.data?.fast_facts.shops).toBe(2)
    expect(store.data?.fast_facts.vacancy_rate).toBeNull()
    expect(store.categoryCounts).toEqual({ fashion: 2 })
    expect(store.loading).toBe(false)
  })

  it('exposes an error instead of falling back to mock data', async () => {
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockRejectedValue(new Error('offline')) }))
    const store = useAnalyticsStore()

    await store.load()

    expect(store.data).toBeNull()
    expect(store.error).toBe('offline')
  })

  it('loads management values and updates the visible card after PATCH', async () => {
    const management = {
      vacancy_rate: 6.25,
      chain_store_rate: 71,
      centrality_index: 154,
      purchasing_power_index: 85,
      reference_date: '2026-06-30',
      updated_at: '2026-08-13T09:00:00Z',
      source: 'Echte Quelle',
      notes: null,
      updated_by_user_id: 'user-1'
    }
    const request = vi.fn()
      .mockResolvedValueOnce(response)
      .mockResolvedValueOnce(management)
      .mockResolvedValueOnce({ ...management, vacancy_rate: 7.5 })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useAnalyticsStore()

    await store.load()
    await store.loadManagement()
    const saved = await store.updateFastFacts({ vacancy_rate: 7.5 })

    expect(saved).toBe(true)
    expect(request).toHaveBeenLastCalledWith('/analytics/fast-facts', {
      method: 'PATCH',
      cache: 'no-store',
      body: JSON.stringify({ vacancy_rate: 7.5 })
    })
    expect(store.data?.fast_facts.vacancy_rate).toBe(7.5)
    expect(store.management?.source).toBe('Echte Quelle')
  })

  it('reports validation and permission errors without changing visible data', async () => {
    const forbidden = Object.assign(new Error('forbidden'), { statusCode: 403 })
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockRejectedValue(forbidden) }))
    const store = useAnalyticsStore()

    const saved = await store.updateFastFacts({ centrality_index: 120 })

    expect(saved).toBe(false)
    expect(store.saveError).toBe('Sie haben keine Berechtigung, diese Kennzahlen zu bearbeiten.')
    expect(store.data).toBeNull()
  })

  it('maps backend validation details to their form fields', async () => {
    const invalid = Object.assign(new Error('invalid'), {
      statusCode: 422,
      details: [{ loc: ['body', 'vacancy_rate'], msg: 'Input should be less than or equal to 100' }]
    })
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockRejectedValue(invalid) }))
    const store = useAnalyticsStore()

    await store.updateFastFacts({ vacancy_rate: 101 })

    expect(store.validationErrors.vacancy_rate).toBe('Input should be less than or equal to 100')
    expect(store.saveError).toBe('Bitte prüfen Sie die eingegebenen Werte.')
  })
})
