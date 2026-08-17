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
    expect(store.activeCategories).toEqual([])
    store.toggleAll()
    expect(store.activeCategories).toHaveLength(industries.length)
    store.toggleAll()
    expect(store.activeCategories).toEqual([])
  })

  it('toggles a single category', () => {
    const store = useFilterStore()
    store.toggleCategory('fashion')
    expect(store.activeCategories).toContain('fashion')
    store.toggleCategory('fashion')
    expect(store.activeCategories).not.toContain('fashion')
  })

  it('supports multi-select, canonical all-state and global reset', () => {
    const store = useFilterStore()
    store.toggleSize('S')
    store.toggleSize('M')
    store.toggleFloor('EG')
    store.toggleFloor('OG')
    store.toggleOccupancy('VACANT')

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
