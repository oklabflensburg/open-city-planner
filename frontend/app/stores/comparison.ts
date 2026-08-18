import { defineStore } from 'pinia'
import type { AnalysisArea } from '~/types/analysisArea'
import type { AreaCompareResult } from '~/types/analytics'
import { gisFilterQuery } from '~/utils/gisFilters'

let comparisonController: AbortController | undefined

export const useComparisonStore = defineStore('comparison', {
  state: () => ({
    availableAreas: [] as AnalysisArea[],
    areasLoading: false,
    areasError: null as string | null,
    result: null as AreaCompareResult | null,
    loading: false,
    error: null as string | null,
    requestId: 0
  }),
  actions: {
    async loadAreas() {
      if (this.availableAreas.length || this.areasLoading) return
      this.areasLoading = true
      this.areasError = null
      try {
        this.availableAreas = await useApi().request<AnalysisArea[]>('/analysis-areas')
      } catch (error) {
        this.areasError = error instanceof Error ? error.message : 'Gebiete konnten nicht geladen werden.'
      } finally {
        this.areasLoading = false
      }
    },
    async compare(areaSlugs: string[], includeBenchmark: boolean) {
      if (!areaSlugs.length) {
        comparisonController?.abort()
        this.result = null
        this.loading = false
        this.error = null
        return
      }
      const current = ++this.requestId
      comparisonController?.abort()
      comparisonController = new AbortController()
      this.loading = true
      this.error = null
      const query = gisFilterQuery(useFilterStore().filterState)
      const values = (key: string) => query.get(key)?.split(',').filter(Boolean) || []
      try {
        const result = await useApi().request<AreaCompareResult>('/analytics/compare', {
          method: 'POST',
          signal: comparisonController.signal,
          body: JSON.stringify({
            area_slugs: areaSlugs,
            include_municipality_benchmark: includeBenchmark,
            filters: {
              categories: values('categories'),
              floors: values('floors'),
              area_sizes: values('area_sizes'),
              occupancy_statuses: values('occupancy_statuses'),
              business_structures: values('business_structures'),
              sources: values('sources')
            }
          })
        })
        if (current === this.requestId) this.result = result
      } catch (error) {
        if (current === this.requestId && !(error instanceof DOMException && error.name === 'AbortError')) {
          this.error = error instanceof Error ? error.message : 'Vergleich konnte nicht geladen werden.'
        }
      } finally {
        if (current === this.requestId) this.loading = false
      }
    },
    reset() {
      comparisonController?.abort()
      comparisonController = undefined
      this.requestId += 1
      this.result = null
      this.loading = false
      this.error = null
    }
  }
})
