import { setActivePinia, createPinia } from 'pinia'
import { describe, expect, it, beforeEach } from 'vitest'
import { useFilterStore } from '~/stores/filter'
import { useMapStore } from '~/stores/map'
import { industries } from '~/utils/industries'

describe('filter store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('hebt einen Branchenfilter vollständig auf', () => {
    const store = useFilterStore()
    expect(store.activeCategories).toHaveLength(industries.length)
    store.setCategories(['fashion'])
    store.resetCategories()
    expect(store.activeCategories).toHaveLength(industries.length)
  })

  it('toggles a single category', () => {
    const store = useFilterStore()
    store.toggleCategory('fashion')
    expect(store.activeCategories).not.toContain('fashion')
    store.toggleCategory('fashion')
    expect(store.activeCategories).toContain('fashion')
  })

  it('behält bei jeder Fachfacette den letzten aktiven Wert bei', () => {
    const store = useFilterStore()
    store.setSizes(['M'])
    store.toggleSize('M')
    store.setFloors(['EG'])
    store.toggleFloor('EG')
    store.setCategories(['fashion'])
    store.toggleCategory('fashion')
    store.setOccupancyStatuses(['VACANT'])
    store.toggleOccupancy('VACANT')
    store.setBusinessStructures(['INDEPENDENT'])
    store.toggleBusinessStructure('INDEPENDENT')

    expect(store.selectedSizes).toEqual(['M'])
    expect(store.selectedFloors).toEqual(['EG'])
    expect(store.activeCategories).toEqual(['fashion'])
    expect(store.occupancyStatuses).toEqual(['VACANT'])
    expect(store.businessStructures).toEqual(['INDEPENDENT'])
  })

  it('koppelt Fachfilter einmalig an das passende Kartenthema', () => {
    const store = useFilterStore()
    const map = useMapStore()

    store.setOccupancyStatuses(['VACANT'])
    expect(map.thematicStyle).toBe('occupancy')
    map.thematicStyle = 'category'
    expect(map.thematicStyle).toBe('category')
    store.setSizes(['S'])
    expect(map.thematicStyle).toBe('size')
    store.setBusinessStructures(['CHAIN'])
    expect(map.thematicStyle).toBe('business')
    store.setCategories(['fashion'])
    expect(map.thematicStyle).toBe('category')
    store.setFloors(['EG'])
    expect(map.thematicStyle).toBe('category')
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
