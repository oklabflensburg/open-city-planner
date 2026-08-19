import { defineStore } from 'pinia'
import { useMapStore } from '~/stores/map'
import { industries, type IndustryKey } from '~/utils/industries'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'
import { BUSINESS_STRUCTURE_OPTIONS, DATA_SOURCE_OPTIONS, defaultGisFilters, FLOOR_OPTIONS, gisFilterKey, gisFilterStateKey, OCCUPANCY_OPTIONS, requiredFacetSelection, SALES_AREA_SIZE_OPTIONS, type FloorGroup, type GisDataSource, type GisFilterState, type SalesAreaSize } from '~/utils/gisFilters'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    favoriteOnly: false,
    selectedSizes: defaultGisFilters().sizes as SalesAreaSize[],
    selectedFloors: defaultGisFilters().floors as FloorGroup[],
    activeCategories: defaultGisFilters().categories as IndustryKey[],
    occupancyStatuses: defaultGisFilters().statuses as OccupancyStatus[],
    businessStructures: defaultGisFilters().businessStructures as BusinessStructure[],
    selectedSources: DATA_SOURCE_OPTIONS.map(item => item.value) as GisDataSource[]
  }),
  getters: {
    allCategoriesActive: state => state.activeCategories.length === industries.length,
    filterState: state => ({
      sizes: state.selectedSizes,
      floors: state.selectedFloors,
      categories: state.activeCategories,
      statuses: state.occupancyStatuses,
      businessStructures: state.businessStructures,
      sources: state.selectedSources
    }) as GisFilterState,
    filterKey(): string {
      return gisFilterKey(this.filterState)
    },
    stateKey(): string {
      return gisFilterStateKey(this.filterState)
    },
    activeFilterCount(): number {
      const groups = [
        [this.selectedSizes.length, SALES_AREA_SIZE_OPTIONS.length],
        [this.selectedFloors.length, FLOOR_OPTIONS.length],
        [this.activeCategories.length, industries.length],
        [this.occupancyStatuses.length, OCCUPANCY_OPTIONS.length],
        [this.businessStructures.length, BUSINESS_STRUCTURE_OPTIONS.length],
        [this.selectedSources.length, DATA_SOURCE_OPTIONS.length]
      ]
      return groups.reduce((count, group) => {
        const selected = group[0] ?? 0
        const total = group[1] ?? 0
        return count + (selected < total ? 1 : 0)
      }, 0)
    },
    canReset(): boolean {
      return this.activeFilterCount > 0
    },
    activeFilterDescriptions(): string[] {
      const descriptions: string[] = []
      const compact = (labels: string[], total: number) => labels.length <= 2 ? labels.join(' + ') : `${labels.length} von ${total}`
      if (this.selectedSizes.length < SALES_AREA_SIZE_OPTIONS.length) descriptions.push(`Fläche: ${compact(this.selectedSizes, SALES_AREA_SIZE_OPTIONS.length)}`)
      if (this.selectedFloors.length < FLOOR_OPTIONS.length) descriptions.push(`Etage: ${this.selectedFloors.join(' + ')}`)
      if (this.activeCategories.length < industries.length) {
        const labels = industries.filter(item => this.activeCategories.includes(item.key)).map(item => item.label)
        descriptions.push(`Branche: ${compact(labels, industries.length)}`)
      }
      if (this.occupancyStatuses.length < OCCUPANCY_OPTIONS.length) {
        const labels = OCCUPANCY_OPTIONS.filter(item => this.occupancyStatuses.includes(item.value)).map(item => item.label)
        descriptions.push(`Status: ${compact(labels, OCCUPANCY_OPTIONS.length)}`)
      }
      if (this.businessStructures.length < BUSINESS_STRUCTURE_OPTIONS.length) {
        const labels = BUSINESS_STRUCTURE_OPTIONS.filter(item => this.businessStructures.includes(item.value)).map(item => item.label)
        descriptions.push(`Betriebsform: ${compact(labels, BUSINESS_STRUCTURE_OPTIONS.length)}`)
      }
      if (this.selectedSources.length === 1) {
        descriptions.push(`Quelle: ${DATA_SOURCE_OPTIONS.find(item => item.value === this.selectedSources[0])?.label}`)
      }
      if (!this.selectedSources.length) descriptions.push('Quelle: keine')
      return descriptions
    }
  },
  actions: {
    setSizes(values: SalesAreaSize[]) {
      this.selectedSizes = requiredFacetSelection(this.selectedSizes, values, SALES_AREA_SIZE_OPTIONS.map(item => item.value))
      useMapStore().thematicStyle = 'size'
    },
    toggleSize(size: SalesAreaSize) {
      this.setSizes(toggleValue(this.selectedSizes, size))
    },
    setFloors(values: FloorGroup[]) {
      this.selectedFloors = requiredFacetSelection(this.selectedFloors, values, FLOOR_OPTIONS.map(item => item.value))
    },
    toggleFloor(floor: FloorGroup) {
      this.setFloors(toggleValue(this.selectedFloors, floor))
    },
    setCategories(values: IndustryKey[]) {
      this.activeCategories = requiredFacetSelection(this.activeCategories, values, industries.map(item => item.key))
      useMapStore().thematicStyle = 'category'
    },
    toggleCategory(category: IndustryKey) {
      this.setCategories(toggleValue(this.activeCategories, category))
    },
    resetCategories() {
      this.setCategories(industries.map(item => item.key))
    },
    setOccupancyStatuses(values: OccupancyStatus[]) {
      this.occupancyStatuses = requiredFacetSelection(this.occupancyStatuses, values, OCCUPANCY_OPTIONS.map(item => item.value))
      useMapStore().thematicStyle = 'occupancy'
    },
    toggleOccupancy(status: OccupancyStatus) {
      this.setOccupancyStatuses(toggleValue(this.occupancyStatuses, status))
    },
    setBusinessStructures(values: BusinessStructure[]) {
      this.businessStructures = requiredFacetSelection(this.businessStructures, values, BUSINESS_STRUCTURE_OPTIONS.map(item => item.value))
      useMapStore().thematicStyle = 'business'
    },
    toggleBusinessStructure(structure: BusinessStructure) {
      this.setBusinessStructures(toggleValue(this.businessStructures, structure))
    },
    setSources(values: GisDataSource[]) {
      this.selectedSources = values.filter(value => DATA_SOURCE_OPTIONS.some(item => item.value === value))
    },
    toggleSource(source: GisDataSource) {
      this.setSources(toggleValue(this.selectedSources, source))
    },
    reset() {
      this.favoriteOnly = false
      this.applyFilters(defaultGisFilters())
    },
    applyFilters(filters: GisFilterState) {
      const defaults = defaultGisFilters()
      this.selectedSizes = requiredFacetSelection(defaults.sizes, filters.sizes, SALES_AREA_SIZE_OPTIONS.map(item => item.value))
      this.selectedFloors = requiredFacetSelection(defaults.floors, filters.floors, FLOOR_OPTIONS.map(item => item.value))
      this.activeCategories = requiredFacetSelection(defaults.categories, filters.categories, industries.map(item => item.key))
      this.occupancyStatuses = requiredFacetSelection(defaults.statuses, filters.statuses, OCCUPANCY_OPTIONS.map(item => item.value))
      this.businessStructures = requiredFacetSelection(defaults.businessStructures, filters.businessStructures, BUSINESS_STRUCTURE_OPTIONS.map(item => item.value))
      this.selectedSources = [...filters.sources]
    }
  }
})

function toggleValue<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter(item => item !== value) : [...values, value]
}
