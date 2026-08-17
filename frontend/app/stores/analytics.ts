import { defineStore } from 'pinia'
import type { AnalyticsOverview, CityMetricsUpdate, CityMetricsVerwaltung, MarketBenchmarkResult } from '~/types/analytics'
import { gisFilterQuery } from '~/utils/gisFilters'

let overviewController: AbortController | undefined
let benchmarkController: AbortController | undefined

export const useAnalyticsStore = defineStore('analytics', {
  state: () => ({
    data: null as AnalyticsOverview | null,
    loading: false,
    error: null as string | null,
    management: null as CityMetricsVerwaltung | null,
    managementLoading: false,
    managementError: null as string | null,
    saving: false,
    saveError: null as string | null,
    validationErrors: {} as Record<string, string>,
    requestId: 0,
    benchmarkRequestId: 0,
    benchmarks: null as MarketBenchmarkResult | null,
    benchmarksLoading: false,
    benchmarksError: null as string | null
  }),
  getters: {
    categoryCounts: state => Object.fromEntries(
      (state.data?.category_counts || []).map(item => [item.category, item.count])
    ) as Record<string, number>
  },
  actions: {
    async load() {
      const currentRequest = ++this.requestId
      const filter = useFilterStore()
      overviewController?.abort()
      overviewController = new AbortController()
      this.loading = true
      this.error = null
      try {
        const query = gisFilterQuery(filter.filterState)
        const areaId = typeof useAnalysisAreasStore === 'function' ? useAnalysisAreasStore().selectedAreaId : null
        if (areaId) query.set('area_id', areaId)
        const suffix = query.size ? `?${query}` : ''
        const result = await useApi().request<AnalyticsOverview>(`/analytics/overview${suffix}`, { signal: overviewController.signal })
        if (currentRequest === this.requestId) this.data = result
      } catch (error) {
        if (currentRequest === this.requestId && !(error instanceof DOMException && error.name === 'AbortError')) {
          this.error = error instanceof Error ? error.message : 'Kennzahlen konnten nicht geladen werden.'
        }
      } finally {
        if (currentRequest === this.requestId) this.loading = false
      }
    },
    async loadBenchmarks() {
      const currentRequest = ++this.benchmarkRequestId
      const filter = useFilterStore()
      benchmarkController?.abort()
      benchmarkController = new AbortController()
      this.benchmarksLoading = true
      this.benchmarksError = null
      try {
        const query = gisFilterQuery(filter.filterState)
        const areaId = typeof useAnalysisAreasStore === 'function' ? useAnalysisAreasStore().selectedAreaId : null
        if (areaId) query.set('area_id', areaId)
        const suffix = query.size ? `?${query}` : ''
        const result = await useApi().request<MarketBenchmarkResult>(`/analytics/benchmarks${suffix}`, { signal: benchmarkController.signal })
        if (currentRequest === this.benchmarkRequestId) this.benchmarks = result
      } catch (error) {
        if (currentRequest === this.benchmarkRequestId && !(error instanceof DOMException && error.name === 'AbortError')) {
          this.benchmarksError = error instanceof Error ? error.message : 'Vergleich konnte nicht geladen werden.'
        }
      } finally {
        if (currentRequest === this.benchmarkRequestId) this.benchmarksLoading = false
      }
    },
    async loadManagement() {
      this.managementLoading = true
      this.managementError = null
      try {
        this.management = await useApi().request<CityMetricsVerwaltung>('/analytics/fast-facts/verwaltung', { cache: 'no-store' })
        return true
      } catch (error) {
        this.managementError = error instanceof Error ? error.message : 'Kennzahlen konnten nicht geladen werden.'
        return false
      } finally {
        this.managementLoading = false
      }
    },
    async updateFastFacts(payload: CityMetricsUpdate) {
      this.saving = true
      this.saveError = null
      this.validationErrors = {}
      try {
        const result = await useApi().request<CityMetricsVerwaltung>('/analytics/fast-facts', {
          method: 'PATCH',
          cache: 'no-store',
          body: JSON.stringify(payload)
        })
        this.management = result
        if (this.data) {
          this.data.fast_facts = {
            ...this.data.fast_facts,
            vacancy_rate: result.vacancy_rate,
            chain_store_rate: result.chain_store_rate,
            centrality_index: result.centrality_index,
            purchasing_power_index: result.purchasing_power_index,
            reference_date: result.reference_date,
            updated_at: result.updated_at
          }
        }
        return true
      } catch (error) {
        const statusCode = typeof error === 'object' && error && 'statusCode' in error ? Number(error.statusCode) : 0
        const details = typeof error === 'object' && error && 'details' in error ? error.details : null
        if (statusCode === 422 && Array.isArray(details)) {
          this.validationErrors = Object.fromEntries(details.flatMap((detail) => {
            const field = Array.isArray(detail?.loc) ? String(detail.loc.at(-1) || '') : ''
            return field ? [[field, String(detail?.msg || 'Ungültiger Wert.')]] : []
          }))
        }
        this.saveError = statusCode === 403
          ? 'Sie haben keine Berechtigung, diese Kennzahlen zu bearbeiten.'
          : statusCode === 422
            ? 'Bitte prüfen Sie die eingegebenen Werte.'
            : 'Die Kennzahlen konnten nicht gespeichert werden.'
        return false
      } finally {
        this.saving = false
      }
    },
    invalidateGisData() {
      overviewController?.abort()
      benchmarkController?.abort()
      overviewController = undefined
      benchmarkController = undefined
      this.requestId += 1
      this.benchmarkRequestId += 1
      this.data = null
      this.benchmarks = null
      this.loading = false
      this.benchmarksLoading = false
      this.error = null
      this.benchmarksError = null
    }
  }
})
