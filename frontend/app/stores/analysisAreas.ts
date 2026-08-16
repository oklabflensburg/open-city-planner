import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { AnalysisArea, AnalysisAreaAnalytics, AnalysisAreaComparison, AnalysisAreaFeatureCollection, AnalysisAreaType, AreaStatistics } from '~/types/analysisArea'
import { useMapStore } from '~/stores/map'

const emptyCollection: AnalysisAreaFeatureCollection = { type: 'FeatureCollection', features: [] }

export const useAnalysisAreasStore = defineStore('analysisAreas', {
  state: () => ({
    areas: [] as AnalysisArea[],
    featureCollection: emptyCollection,
    analytics: null as AnalysisAreaAnalytics | null,
    comparison: null as AnalysisAreaComparison | null,
    statistics: null as AreaStatistics | null,
    loading: false,
    detailsLoading: false,
    error: null as string | null,
    visibility: { MUNICIPALITY: true, DISTRICT: true, QUARTER: true } as Record<AnalysisAreaType, boolean>,
    requestId: 0
  }),
  getters: {
    selectedAreaId(): string | null {
      const entity = useMapStore().selectedMapEntity
      return entity?.type === 'analysis-area' ? entity.id : null
    },
    selectedArea(state): AnalysisArea | null {
      return state.areas.find(area => area.id === this.selectedAreaId) || null
    }
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
    async loadDetails(selectedId?: string) {
      const id = selectedId || this.selectedAreaId
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
        const selectedArea = this.areas.find(area => area.id === id)
        const [analytics, comparison, statistics] = await Promise.all([
          api.request<AnalysisAreaAnalytics>(`/analysis-areas/${id}/analytics?${query}`),
          api.request<AnalysisAreaComparison>(`/analysis-areas/${id}/comparison?${query}`),
          selectedArea ? api.request<AreaStatistics>(`/analysis-areas/by-slug/${encodeURIComponent(selectedArea.slug)}/statistics`) : Promise.resolve(null)
        ])
        if (current === this.requestId && this.selectedAreaId === id) {
          this.analytics = analytics
          this.comparison = comparison
          this.statistics = statistics
        }
      } catch (error) {
        if (current === this.requestId) this.error = error instanceof Error ? error.message : 'Gebietsanalyse konnte nicht geladen werden.'
      } finally {
        if (current === this.requestId) this.detailsLoading = false
      }
    },
    clearSelection() {
      this.analytics = null
      this.comparison = null
      this.statistics = null
      this.detailsLoading = false
      this.error = null
      this.requestId++
    }
  }
})
