import { defineStore } from 'pinia'
import { defaultActiveIndustries, industries, type IndustryKey } from '~/utils/industries'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    favoriteOnly: false,
    selectedSize: 'M' as 'S' | 'M' | 'L' | 'XL',
    selectedFloor: 'EG' as 'UG' | 'EG' | 'OG',
    activeCategories: [...defaultActiveIndustries] as IndustryKey[],
    occupancyStatuses: [] as OccupancyStatus[],
    businessStructures: [] as BusinessStructure[]
  }),
  getters: {
    allCategoriesActive: (state) => state.activeCategories.length === industries.length
  },
  actions: {
    toggleCategory(category: IndustryKey) {
      this.activeCategories = this.activeCategories.includes(category)
        ? this.activeCategories.filter((item) => item !== category)
        : [...this.activeCategories, category]
    },
    toggleAll() {
      this.activeCategories = this.allCategoriesActive ? [] : [...defaultActiveIndustries]
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
    reset() {
      this.favoriteOnly = false
      this.selectedSize = 'M'
      this.selectedFloor = 'EG'
      this.activeCategories = [...defaultActiveIndustries]
      this.occupancyStatuses = []
      this.businessStructures = []
    }
  }
})
