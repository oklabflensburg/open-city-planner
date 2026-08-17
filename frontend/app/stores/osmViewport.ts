import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { OsmBounds, OsmFeatureCategory, OsmFeatureDetail, OsmViewportFeature, OsmViewportResult } from '~/types/osm'
import { osmPoiCategories } from '~/utils/osmCategories'
import { useMapStore } from '~/stores/map'
import { useFilterStore } from '~/stores/filter'
import { gisFilterQuery } from '~/utils/gisFilters'

const VIEWPORT_BUFFER_RATIO = 0.2
const VIEWPORT_CACHE_SIZE = 4

type CachedViewport = {
  data: OsmViewportResult
  bounds: OsmBounds
  zoomBucket: number
  filterKey: string
  payloadBytes: number
}

export function expandOsmBounds(bounds: OsmBounds, ratio = VIEWPORT_BUFFER_RATIO): OsmBounds {
  const longitudePadding = (bounds.east - bounds.west) * ratio
  const latitudePadding = (bounds.north - bounds.south) * ratio
  return {
    west: Math.max(-180, bounds.west - longitudePadding),
    south: Math.max(-90, bounds.south - latitudePadding),
    east: Math.min(180, bounds.east + longitudePadding),
    north: Math.min(90, bounds.north + latitudePadding)
  }
}

function containsBounds(container: OsmBounds | null, viewport: OsmBounds) {
  return Boolean(container
    && viewport.west >= container.west && viewport.south >= container.south
    && viewport.east <= container.east && viewport.north <= container.north)
}

function zoomBucket(zoom: number) {
  return Math.floor(zoom)
}

export const useOsmViewportStore = defineStore('osmViewport', {
  state: () => ({
    showPois: true,
    showAreas: true,
    showBuildings: false,
    activeCategories: osmPoiCategories.map(item => item.key) as OsmFeatureCategory[],
    data: null as OsmViewportResult | null,
    loading: false,
    error: null as string | null,
    detail: null as OsmFeatureDetail | null,
    detailLoading: false,
    detailError: null as string | null,
    detailRequestId: 0,
    lastRenderDurationMs: null as number | null,
    generation: 0,
    lastRequestKey: '',
    dataRequestKey: '',
    loadedBounds: null as OsmBounds | null,
    loadedZoomBucket: -1,
    loadedFilterKey: '',
    viewportCache: markRaw(new Map<string, CachedViewport>()),
    viewportCacheBytes: 0,
    controller: null as AbortController | null
  }),
  getters: {
    selectedFeature(): OsmViewportFeature | null {
      const entity = useMapStore().selectedMapEntity
      return entity?.type === 'osm' ? entity.feature : null
    },
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
      const mobile = import.meta.client && window.matchMedia('(max-width: 767px)').matches
      const limit = mobile ? 800 : zoom < 15 ? 800 : zoom < 17 ? 1200 : 2000
      const query = gisFilterQuery(useFilterStore().filterState)
      query.set('west', bounds.west.toFixed(6))
      query.set('south', bounds.south.toFixed(6))
      query.set('east', bounds.east.toFixed(6))
      query.set('north', bounds.north.toFixed(6))
      query.set('zoom', zoom.toFixed(2))
      query.set('osm_categories', categories.join(','))
      query.set('buildings', String(this.showBuildings))
      query.set('limit', String(limit))
      return query.toString()
    },
    viewportFilterKey() {
      return `${this.requestedCategories.slice().sort().join(',')}|${this.showBuildings}|${useFilterStore().filterKey}`
    },
    hasCacheFor(bounds: OsmBounds, zoom: number) {
      return Boolean(this.data && this.dataRequestKey === this.viewportRequestKey(bounds, zoom))
    },
    covers(bounds: OsmBounds, zoom: number) {
      return Boolean(this.data
        && this.loadedZoomBucket === zoomBucket(zoom)
        && this.loadedFilterKey === this.viewportFilterKey()
        && containsBounds(this.loadedBounds, bounds))
    },
    async load(bounds: OsmBounds, zoom: number, options: { force?: boolean } = {}) {
      const categories = this.requestedCategories
      const osmEnabled = useFilterStore().selectedSources.includes('OSM')
      const key = this.viewportRequestKey(bounds, zoom)
      const filterKey = this.viewportFilterKey()
      const bucket = zoomBucket(zoom)
      if (!categories.length || !osmEnabled) {
        this.controller?.abort()
        this.controller = null
        this.loading = false
        this.lastRequestKey = key
        this.dataRequestKey = key
        this.loadedBounds = bounds
        this.loadedZoomBucket = bucket
        this.loadedFilterKey = filterKey
        const empty: OsmViewportResult = {
          type: 'FeatureCollection', features: [],
          meta: {
            count: 0, truncated: false, zoom, summary: {}, canonical_summary: {}, canonical_facets: {},
            business_count: 0, context_count: 0, deduplicated_linked_count: 0,
            osm_data_updated_at: null
          }
        }
        this.data = markRaw(empty)
        return this.data
      }
      if (!options.force && key === this.lastRequestKey && (this.loading || this.dataRequestKey === key)) return this.data
      const cached = !options.force ? this.viewportCache.get(key) : undefined
      if (cached) {
        this.viewportCache.delete(key)
        this.viewportCache.set(key, cached)
        this.data = cached.data
        this.dataRequestKey = key
        this.lastRequestKey = key
        this.loadedBounds = cached.bounds
        this.loadedZoomBucket = cached.zoomBucket
        this.loadedFilterKey = cached.filterKey
        return cached.data
      }
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
          const data = markRaw(result)
          // Conservative heap estimate without serializing the full collection again on the main thread.
          const payloadBytes = result.features.length * 512
          this.data = data
          this.dataRequestKey = key
          this.loadedBounds = bounds
          this.loadedZoomBucket = bucket
          this.loadedFilterKey = filterKey
          const previous = this.viewportCache.get(key)
          if (previous) this.viewportCacheBytes -= previous.payloadBytes
          this.viewportCache.delete(key)
          this.viewportCache.set(key, markRaw({ data, bounds, zoomBucket: bucket, filterKey, payloadBytes }))
          this.viewportCacheBytes += payloadBytes
          while (this.viewportCache.size > VIEWPORT_CACHE_SIZE) {
            const oldestKey = this.viewportCache.keys().next().value
            if (!oldestKey) break
            const oldest = this.viewportCache.get(oldestKey)
            if (oldest) this.viewportCacheBytes -= oldest.payloadBytes
            this.viewportCache.delete(oldestKey)
          }
        }
      } catch (error) {
        if (generation === this.generation && !controller.signal.aborted) {
          this.lastRequestKey = ''
          this.error = error instanceof Error ? error.message : 'OSM-Objekte konnten nicht geladen werden.'
        }
      } finally {
        if (generation === this.generation) this.loading = false
      }
      return generation === this.generation && !controller.signal.aborted ? this.data : null
    },
    async loadDetail(feature: OsmViewportFeature) {
      const requestId = ++this.detailRequestId
      this.detail = null
      this.detailError = null
      this.detailLoading = true
      try {
        const detail = await useApi().request<OsmFeatureDetail>(`/osm/features/${feature.properties.osm_type}/${feature.properties.osm_id}`)
        if (requestId === this.detailRequestId && this.selectedFeature?.id === feature.id) this.detail = detail
      } catch (error) {
        if (requestId === this.detailRequestId && this.selectedFeature?.id === feature.id) {
          this.detailError = error instanceof Error ? error.message : 'Details konnten nicht geladen werden.'
        }
      } finally {
        if (requestId === this.detailRequestId && this.selectedFeature?.id === feature.id) this.detailLoading = false
      }
    },
    clearSelection() {
      this.detailRequestId++
      this.detail = null
      this.detailError = null
      this.detailLoading = false
    },
    invalidateForPolygonMutation() {
      this.controller?.abort()
      this.controller = null
      this.generation += 1
      this.data = null
      this.loading = false
      this.error = null
      this.lastRequestKey = ''
      this.dataRequestKey = ''
      this.loadedBounds = null
      this.loadedZoomBucket = -1
      this.loadedFilterKey = ''
      this.viewportCache = markRaw(new Map<string, CachedViewport>())
      this.viewportCacheBytes = 0
      this.clearSelection()
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
