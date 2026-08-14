import { defineStore } from 'pinia'
import type { OsmBounds, OsmFeatureCategory, OsmFeatureDetail, OsmViewportFeature, OsmViewportResult } from '~/types/osm'
import { osmPoiCategories } from '~/utils/osmCategories'

export const useOsmViewportStore = defineStore('osmViewport', {
  state: () => ({
    showPois: true,
    showAreas: true,
    showBuildings: false,
    activeCategories: osmPoiCategories.map(item => item.key) as OsmFeatureCategory[],
    data: null as OsmViewportResult | null,
    loading: false,
    error: null as string | null,
    selectedFeature: null as OsmViewportFeature | null,
    detail: null as OsmFeatureDetail | null,
    detailLoading: false,
    detailError: null as string | null,
    lastRenderDurationMs: null as number | null,
    generation: 0,
    lastRequestKey: '',
    dataRequestKey: '',
    controller: null as AbortController | null
  }),
  getters: {
    requestedCategories(state): OsmFeatureCategory[] {
      return [
        ...(state.showPois ? state.activeCategories : []),
        ...(state.showAreas ? ['landuse' as const] : []),
        ...(state.showBuildings ? ['building' as const] : [])
      ]
    }
  },
  actions: {
    toggleCategory(category: OsmFeatureCategory) {
      this.activeCategories = this.activeCategories.includes(category)
        ? this.activeCategories.filter(item => item !== category)
        : [...this.activeCategories, category]
    },
    viewportRequestKey(bounds: OsmBounds, zoom: number) {
      const categories = this.requestedCategories
      const query = new URLSearchParams({
        west: bounds.west.toFixed(6), south: bounds.south.toFixed(6),
        east: bounds.east.toFixed(6), north: bounds.north.toFixed(6), zoom: zoom.toFixed(2),
        categories: categories.join(','), buildings: String(this.showBuildings), limit: '2500'
      })
      return query.toString()
    },
    hasCacheFor(bounds: OsmBounds, zoom: number) {
      return Boolean(this.data && this.dataRequestKey === this.viewportRequestKey(bounds, zoom))
    },
    async load(bounds: OsmBounds, zoom: number, options: { force?: boolean } = {}) {
      const categories = this.requestedCategories
      const key = this.viewportRequestKey(bounds, zoom)
      if (!categories.length) {
        this.controller?.abort()
        this.controller = null
        this.loading = false
        this.lastRequestKey = key
        this.dataRequestKey = key
        this.data = { type: 'FeatureCollection', features: [], meta: { count: 0, truncated: false, zoom, summary: {}, osm_data_updated_at: null } }
        return this.data
      }
      if (!options.force && key === this.lastRequestKey && (this.loading || this.dataRequestKey === key)) return this.data
      this.lastRequestKey = key
      this.controller?.abort()
      const controller = new AbortController()
      this.controller = controller
      const generation = ++this.generation
      this.loading = true
      this.error = null
      try {
        const result = await useApi().request<OsmViewportResult>(`/osm/features?${key}`, { signal: controller.signal })
        if (generation === this.generation) {
          this.data = result
          this.dataRequestKey = key
        }
      } catch (error) {
        if (generation === this.generation && !controller.signal.aborted) {
          this.lastRequestKey = ''
          this.error = error instanceof Error ? error.message : 'OSM-Objekte konnten nicht geladen werden.'
        }
      } finally {
        if (generation === this.generation) this.loading = false
      }
      return this.data
    },
    async select(feature: OsmViewportFeature) {
      this.selectedFeature = feature
      this.detail = null
      this.detailError = null
      this.detailLoading = true
      try {
        this.detail = await useApi().request<OsmFeatureDetail>(`/osm/features/${feature.properties.osm_type}/${feature.properties.osm_id}`)
      } catch (error) {
        this.detailError = error instanceof Error ? error.message : 'Details konnten nicht geladen werden.'
      } finally {
        this.detailLoading = false
      }
    },
    clearSelection() {
      this.selectedFeature = null
      this.detail = null
      this.detailError = null
    },
    setRenderDuration(value: number) {
      this.lastRenderDurationMs = Math.round(value)
    },
    reset() {
      this.showPois = true
      this.showAreas = true
      this.showBuildings = false
      this.activeCategories = osmPoiCategories.map(item => item.key)
    },
    dispose() {
      this.controller?.abort()
      this.controller = null
      this.generation += 1
      this.loading = false
      this.lastRequestKey = ''
    }
  }
})
