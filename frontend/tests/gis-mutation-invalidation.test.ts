import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGisInvalidation } from '~/composables/useGisInvalidation'
import { useAnalyticsStore } from '~/stores/analytics'
import { useMapStore } from '~/stores/map'
import { useNotificationsStore } from '~/stores/notifications'
import { useOsmViewportStore } from '~/stores/osmViewport'
import { usePolygonStore } from '~/stores/polygon'

describe('central GIS mutation invalidation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('usePolygonStore', usePolygonStore)
    vi.stubGlobal('useOsmViewportStore', useOsmViewportStore)
    vi.stubGlobal('useAnalyticsStore', useAnalyticsStore)
    vi.stubGlobal('useMapStore', useMapStore)
    vi.stubGlobal('useNotificationsStore', useNotificationsStore)
  })

  it('invalidates polygon, OSM, analytics and stale selection after OSM adoption', () => {
    const polygons = usePolygonStore()
    const osm = useOsmViewportStore()
    const analytics = useAnalyticsStore()
    const map = useMapStore()
    polygons.loadedFilterKey = 'same-filter'
    osm.data = { type: 'FeatureCollection', features: [], meta: {
      count: 0, truncated: false, zoom: 17, summary: {}, canonical_summary: {}, canonical_facets: {},
      business_count: 0, context_count: 0, deduplicated_linked_count: 0, osm_data_updated_at: null
    } }
    osm.viewportCache.set('same-viewport', {
      data: osm.data, bounds: { west: 9.4, south: 54.7, east: 9.5, north: 54.8 },
      zoomBucket: 17, filterKey: 'same-filter', payloadBytes: 100
    })
    analytics.data = { fast_facts: { polygon_count: 46 } } as never
    map.selectedMapEntity = { type: 'osm', feature: {
      type: 'Feature', id: 'way/123', geometry: { type: 'Point', coordinates: [9.43, 54.78] },
      properties: {
        feature_id: 'way/123', osm_type: 'way', osm_id: 123, category: 'retail',
        canonical_category: 'fashion', name: 'OSM Mode', primary_type: 'clothes',
        feature_type: 'point', source: 'OSM', canonical_floor: 'EG', mapped_area_m2: null,
        occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: []
      }
    } }
    const generation = map.gisDataGeneration

    useGisInvalidation().invalidateAfterPolygonMutation({
      type: 'ADOPT', polygonId: 'new-polygon', osmType: 'way', osmId: 123
    })

    expect(polygons.loadedFilterKey).toBeNull()
    expect(osm.data).toBeNull()
    expect(osm.viewportCache.size).toBe(0)
    expect(analytics.data).toBeNull()
    expect(map.selectedMapEntity).toBeNull()
    expect(map.gisDataDirty).toBe(true)
    expect(map.gisDataGeneration).toBe(generation + 1)
  })

  it('removes deleted polygons optimistically but keeps create/update lists until the fresh overview', () => {
    const polygons = usePolygonStore()
    polygons.polygons = [{ id: 'existing' }, { id: 'other' }] as never
    const invalidation = useGisInvalidation()

    invalidation.invalidateAfterPolygonMutation({ type: 'UPDATE', polygonId: 'existing' })
    expect(polygons.polygons.map(item => item.id)).toEqual(['existing', 'other'])

    invalidation.invalidateAfterPolygonMutation({ type: 'DELETE', polygonId: 'existing' })
    expect(polygons.polygons.map(item => item.id)).toEqual(['other'])
    expect(polygons.loadedFilterKey).toBeNull()
  })
})

