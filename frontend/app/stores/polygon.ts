import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { PolygonMetrics, PolygonOverview } from '~/types/geo'
import type { PolygonOsmInfo } from '~/types/osm'
import { useMapStore } from '~/stores/map'
import { gisFilterQuery } from '~/utils/gisFilters'

let overviewController: AbortController | undefined

export const usePolygonStore = defineStore('polygon', {
  state: () => ({
    polygons: [] as PolygonOverview[],
    selectedMetrics: null as PolygonMetrics | null,
    selectedOsmInfo: null as PolygonOsmInfo | null,
    metricsLoading: false,
    metricsError: null as string | null,
    osmLoading: false,
    osmError: null as string | null,
    selectionRequestId: 0,
    loading: false,
    saving: false,
    error: null as string | null,
    overviewRequestId: 0,
    loadedFilterKey: null as string | null,
    saveState: 'idle' as 'idle' | 'saving' | 'saved' | 'error'
  }),
  getters: {
    selectedPolygonId: () => {
      const entity = useMapStore().selectedMapEntity
      return entity?.type === 'polygon' ? entity.id : null
    },
    selectedPolygon(state): PolygonOverview | null {
      return state.polygons.find(polygon => polygon.id === this.selectedPolygonId) || null
    },
    featureCollection: (state) => ({
      type: 'FeatureCollection' as const,
      features: state.polygons.map((polygon) => ({
        type: 'Feature' as const,
        id: polygon.id,
        geometry: polygon.geometry,
        properties: {
          id: polygon.id,
          name: polygon.name,
          category: polygon.category,
          floor: polygon.floor,
          size: polygon.area_size,
          slug: polygon.slug,
          address: polygon.address_display_name,
          occupancy_status: polygon.occupancy_status,
          business_structure: polygon.business_structure
        }
      }))
    })
  },
  actions: {
    async loadPolygons(options: { force?: boolean } = {}) {
      const filter = useFilterStore()
      const key = filter.filterKey
      if (!options.force && this.loadedFilterKey === key) return
      if (!filter.selectedSources.includes('STADTPLANNER')) {
        overviewController?.abort()
        this.overviewRequestId++
        this.polygons = []
        this.loadedFilterKey = key
        this.loading = false
        this.error = null
        return
      }
      const requestId = ++this.overviewRequestId
      overviewController?.abort()
      overviewController = new AbortController()
      this.loading = true
      this.error = null
      try {
        const query = gisFilterQuery(filter.filterState).toString()
        const polygons = await usePolygonApi().overview(query, overviewController.signal)
        if (requestId !== this.overviewRequestId) return
        this.polygons = markRaw(polygons)
        this.loadedFilterKey = key
      } catch (error) {
        if (requestId === this.overviewRequestId && !(error instanceof DOMException && error.name === 'AbortError')) {
          this.error = error instanceof Error ? error.message : 'Polygone konnten nicht geladen werden.'
        }
      } finally {
        if (requestId === this.overviewRequestId) this.loading = false
      }
    },
    async loadSelection(id: string) {
      const requestId = ++this.selectionRequestId
      this.selectedMetrics = null
      this.selectedOsmInfo = null
      this.metricsLoading = true
      this.osmLoading = true
      this.metricsError = null
      this.osmError = null
      const polygon = this.polygons.find(item => item.id === id)
      const api = usePolygonApi()
      const metricsRequest = api.metrics(id).then((metrics) => {
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.selectedMetrics = metrics
      }).catch((error) => {
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) {
          this.metricsError = error instanceof Error ? error.message : 'Kennzahlen konnten nicht geladen werden.'
        }
      }).finally(() => {
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.metricsLoading = false
      })
      const osmRequest = polygon
        ? api.osmBySlug(polygon.slug).then((info) => {
            if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.selectedOsmInfo = info
          }).catch((error) => {
            if (requestId === this.selectionRequestId && this.selectedPolygonId === id) {
              this.osmError = error instanceof Error ? error.message : 'OpenStreetMap-Daten konnten nicht geladen werden.'
            }
          }).finally(() => {
            if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.osmLoading = false
          })
        : Promise.resolve().then(() => {
            if (requestId === this.selectionRequestId) {
              this.osmLoading = false
              this.osmError = 'OpenStreetMap-Daten konnten nicht geladen werden.'
            }
          })
      await Promise.all([metricsRequest, osmRequest])
    },
    async retryOsm(id: string) {
      const polygon = this.polygons.find(item => item.id === id)
      if (!polygon || this.selectedPolygonId !== id) return
      const requestId = this.selectionRequestId
      this.osmLoading = true
      this.osmError = null
      try {
        const info = await usePolygonApi().osmBySlug(polygon.slug)
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.selectedOsmInfo = info
      } catch (error) {
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) {
          this.osmError = error instanceof Error ? error.message : 'OpenStreetMap-Daten konnten nicht geladen werden.'
        }
      } finally {
        if (requestId === this.selectionRequestId && this.selectedPolygonId === id) this.osmLoading = false
      }
    },
    clearSelection() {
      this.selectionRequestId++
      this.selectedMetrics = null
      this.selectedOsmInfo = null
      this.metricsLoading = false
      this.osmLoading = false
      this.metricsError = null
      this.osmError = null
    },
    invalidateForPolygonMutation(removedId?: string) {
      overviewController?.abort()
      overviewController = undefined
      this.overviewRequestId += 1
      if (removedId) {
        this.polygons = markRaw(this.polygons.filter(polygon => polygon.id !== removedId))
      }
      this.loadedFilterKey = null
      this.loading = false
      this.error = null
      if (removedId && this.selectedPolygonId === removedId) {
        useMapStore().selectedMapEntity = null
        this.clearSelection()
      }
    },
    invalidateDeletedPolygon(id: string) {
      this.invalidateForPolygonMutation(id)
    }
  }
})
