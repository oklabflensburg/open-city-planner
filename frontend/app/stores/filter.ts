import { defineStore } from 'pinia'
import { industries, type IndustryKey } from '~/utils/industries'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'
import { BUSINESS_STRUCTURE_OPTIONS, DATA_SOURCE_OPTIONS, defaultGisFilters, FLOOR_OPTIONS, gisFilterKey, gisFilterStateKey, OCCUPANCY_OPTIONS, SALES_AREA_SIZE_OPTIONS, type FloorGroup, type GisDataSource, type GisFilterState, type SalesAreaSize } from '~/utils/gisFilters'

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
    }
  },
  actions: {
    toggleSize(size: SalesAreaSize) {
      this.selectedSizes = toggleValue(this.selectedSizes, size)
    },
    toggleFloor(floor: FloorGroup) {
      this.selectedFloors = toggleValue(this.selectedFloors, floor)
    },
    toggleCategory(category: IndustryKey) {
      this.activeCategories = this.activeCategories.includes(category)
        ? this.activeCategories.filter((item) => item !== category)
        : [...this.activeCategories, category]
    },
    toggleAll() {
      this.activeCategories = this.allCategoriesActive ? [] : industries.map(item => item.key)
    },
    toggleOccupancy(status: OccupancyStatus) {
      this.occupancyStatuses = this.occupancyStatuses.includes(status)
        ? this.occupancyStatuses.filter(item => item !== status)
        : [...this.occupancyStatuses, status]
    },
    toggleBusinessStructure(structure: BusinessStructure) {
      this.businessStructures = this.businessStructures.includes(structure)
        ? this.businessStructures.filter(item => item !== structure)
        : [...this.businessStructures, structure]
    },
    toggleSource(source: GisDataSource) {
      this.selectedSources = toggleValue(this.selectedSources, source)
    },
    reset() {
      this.favoriteOnly = false
      this.applyFilters(defaultGisFilters())
    },
    applyFilters(filters: GisFilterState) {
      this.selectedSizes = [...filters.sizes]
      this.selectedFloors = [...filters.floors]
      this.activeCategories = [...filters.categories]
      this.occupancyStatuses = [...filters.statuses]
      this.businessStructures = [...filters.businessStructures]
      this.selectedSources = [...filters.sources]
    }
  }
})

function toggleValue<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter(item => item !== value) : [...values, value]
}
