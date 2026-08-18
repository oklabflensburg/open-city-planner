import { setActivePinia, createPinia } from 'pinia'
import { describe, expect, it, beforeEach } from 'vitest'
import { useFilterStore } from '~/stores/filter'
import { industries } from '~/utils/industries'

describe('filter store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('toggles all industry categories', () => {
    const store = useFilterStore()
    expect(store.activeCategories).toHaveLength(industries.length)
    store.toggleAll()
    expect(store.activeCategories).toEqual([])
    store.toggleAll()
    expect(store.activeCategories).toHaveLength(industries.length)
  })

  it('toggles a single category', () => {
    const store = useFilterStore()
    store.toggleCategory('fashion')
    expect(store.activeCategories).not.toContain('fashion')
    store.toggleCategory('fashion')
    expect(store.activeCategories).toContain('fashion')
  })

  it('supports multi-select, canonical all-state and global reset', () => {
    const store = useFilterStore()
    store.selectedSizes = ['S', 'M']
    store.selectedFloors = ['EG', 'OG']
    store.occupancyStatuses = ['VACANT']

    expect(store.selectedSizes).toEqual(['S', 'M'])
    expect(store.selectedFloors).toEqual(['EG', 'OG'])
    expect(store.activeFilterCount).toBe(3)
    expect(store.filterKey).toContain('area_sizes=S%2CM')

    store.reset()
    expect(store.filterKey).toBe('')
    expect(store.activeFilterCount).toBe(0)
    expect(store.selectedSources).toEqual(['STADTPLANNER', 'OSM'])
  })
})
