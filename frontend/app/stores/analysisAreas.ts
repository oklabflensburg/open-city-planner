import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { AnalysisArea, AnalysisAreaAnalytics, AnalysisAreaComparison, AnalysisAreaFeatureCollection, AnalysisAreaType } from '~/types/analysisArea'

const emptyCollection: AnalysisAreaFeatureCollection = { type: 'FeatureCollection', features: [] }

export const useAnalysisAreasStore = defineStore('analysisAreas', {
  state: () => ({
    areas: [] as AnalysisArea[],
    featureCollection: emptyCollection,
    selectedAreaId: null as string | null,
    analytics: null as AnalysisAreaAnalytics | null,
    comparison: null as AnalysisAreaComparison | null,
    loading: false,
    detailsLoading: false,
    error: null as string | null,
    visibility: { MUNICIPALITY: true, DISTRICT: true, QUARTER: true } as Record<AnalysisAreaType, boolean>,
    requestId: 0
  }),
  getters: {
    selectedArea: state => state.areas.find(area => area.id === state.selectedAreaId) || null
  },
  actions: {
    async load() {
      if (this.areas.length && this.featureCollection.features.length) return
      this.loading = true
      this.error = null
      try {
        const api = useApi()
        const [areas, featureCollection] = await Promise.all([
          api.request<AnalysisArea[]>('/analysis-areas'),
          api.request<AnalysisAreaFeatureCollection>('/analysis-areas/geojson')
        ])
        this.areas = markRaw(areas)
        this.featureCollection = markRaw(featureCollection)
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'Gebietsgrenzen konnten nicht geladen werden.'
      } finally {
        this.loading = false
      }
    },
    async select(id: string) {
      this.selectedAreaId = id
      await this.loadDetails()
    },
    async loadDetails() {
      const id = this.selectedAreaId
      if (!id) return
      const current = ++this.requestId
      this.detailsLoading = true
      this.error = null
      try {
        const filter = useFilterStore()
        const query = new URLSearchParams({
          categories: filter.activeCategories.length ? filter.activeCategories.join(',') : '__none__',
          floors: filter.selectedFloor,
          area_sizes: filter.selectedSize
        })
        if (filter.occupancyStatuses.length) query.set('occupancy_statuses', filter.occupancyStatuses.join(','))
        if (filter.businessStructures.length) query.set('business_structures', filter.businessStructures.join(','))
        const api = useApi()
        const [analytics, comparison] = await Promise.all([
          api.request<AnalysisAreaAnalytics>(`/analysis-areas/${id}/analytics?${query}`),
          api.request<AnalysisAreaComparison>(`/analysis-areas/${id}/comparison?${query}`)
        ])
        if (current === this.requestId && this.selectedAreaId === id) {
          this.analytics = analytics
          this.comparison = comparison
        }
      } catch (error) {
        if (current === this.requestId) this.error = error instanceof Error ? error.message : 'Gebietsanalyse konnte nicht geladen werden.'
      } finally {
        if (current === this.requestId) this.detailsLoading = false
      }
    },
    clearSelection() {
      this.selectedAreaId = null
      this.analytics = null
      this.comparison = null
      this.requestId++
    }
  }
})
