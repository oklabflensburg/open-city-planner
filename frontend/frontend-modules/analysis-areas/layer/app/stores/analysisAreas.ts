import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { AnalysisArea, AnalysisAreaAnalytics, AnalysisAreaComparison, AnalysisAreaFeatureCollection, AnalysisAreaType, AreaStatistics } from '../types/analysisArea'
import { useMapFilterPort, useModuleHttp } from '#frontend-module-sdk'

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
    presentedAreaId: null as string | null,
    error: null as string | null,
    visibility: { MUNICIPALITY: true, DISTRICT: true, QUARTER: true } as Record<AnalysisAreaType, boolean>,
    requestId: 0
  }),
  getters: {
    selectedAreaId(): string | null {
      return this.presentedAreaId
    },
    selectedArea(state): AnalysisArea | null {
      return state.areas.find(area => area.id === this.selectedAreaId) || null
    }
  },
  actions: {
    async presentSelection(id: string) {
      this.presentedAreaId = id
      await this.loadDetails(id)
    },
    async load() {
      if (this.areas.length && this.featureCollection.features.length) return
      this.loading = true
      this.error = null
      try {
        const api = useModuleHttp()
        const [areas, featureCollection] = await Promise.all([
          api.request<AnalysisArea[]>('/analysis-areas'),
          api.request<AnalysisAreaFeatureCollection>('/analysis-areas/geojson?limit=1000')
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
        const query = useMapFilterPort().toQuery()
        const suffix = query.size ? `?${query}` : ''
        const api = useModuleHttp()
        const selectedArea = this.areas.find(area => area.id === id)
        const [analytics, comparison, statistics] = await Promise.all([
          api.request<AnalysisAreaAnalytics>(`/analysis-areas/${id}/analytics${suffix}`),
          api.request<AnalysisAreaComparison>(`/analysis-areas/${id}/comparison${suffix}`),
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
      this.presentedAreaId = null
      this.analytics = null
      this.comparison = null
      this.statistics = null
      this.detailsLoading = false
      this.error = null
      this.requestId++
    }
  }
})
