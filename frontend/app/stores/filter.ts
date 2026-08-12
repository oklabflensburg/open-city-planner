import { defineStore } from 'pinia'
import { defaultActiveIndustries, industries, type IndustryKey } from '~/utils/industries'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    favoriteOnly: false,
    selectedSize: 'M' as 'S' | 'M' | 'L' | 'XL',
    selectedFloor: 'EG' as 'UG' | 'EG' | 'OG',
    activeCategories: [...defaultActiveIndustries] as IndustryKey[]
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
    }
  }
})

