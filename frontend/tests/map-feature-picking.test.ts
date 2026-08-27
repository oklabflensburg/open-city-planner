import type { Map, MapGeoJSONFeature } from 'maplibre-gl'
import { describe, expect, it, vi } from 'vitest'
import { MAP_INTERACTIVE_LAYERS, pickMapEntityAtPoint } from '~/utils/mapFeaturePicking'

function renderedFeature(layerId: string, properties: Record<string, unknown>, coordinates: [number, number] = [20, 20], multi = false) {
  const isPolygon = layerId.endsWith('-fill')
  return {
    type: 'Feature',
    geometry: isPolygon
      ? multi
        ? { type: 'MultiPolygon', coordinates: [[[[9, 54], [10, 54], [10, 55], [9, 54]]]] }
        : { type: 'Polygon', coordinates: [[[9, 54], [10, 54], [10, 55], [9, 54]]] }
      : { type: 'Point', coordinates },
    properties,
    layer: { id: layerId },
    source: 'test',
    state: {}
  } as unknown as MapGeoJSONFeature
}

function pickingMap(hits: Record<string, MapGeoJSONFeature[]>) {
  const queryRenderedFeatures = vi.fn((_geometry, options: { layers?: string[] }) => (
    (options.layers || []).flatMap(layerId => hits[layerId] || [])
  ))
  const map = {
    getLayer: (id: string) => ({ id }),
    queryRenderedFeatures,
    project: ([x, y]: [number, number]) => ({ x, y })
  } as unknown as Pick<Map, 'getLayer' | 'project' | 'queryRenderedFeatures'>
  return { map, queryRenderedFeatures }
}

describe('central map feature picking', () => {
  it('selects the closest point POI over every polygon at the tap location', () => {
    const farPoi = renderedFeature('osm-poi-circle', { feature_id: 'far' }, [30, 30])
    const nearPoi = renderedFeature('osm-poi-circle', { feature_id: 'near' }, [21, 21])
    const { map } = pickingMap({
      'osm-poi-circle': [farPoi, nearPoi],
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'area' })],
      'overview-polygons-fill': [renderedFeature('overview-polygons-fill', { id: 'polygon' })]
    })

    const result = pickMapEntityAtPoint(map, { x: 20, y: 20 }, 12)

    expect(result?.kind).toBe('point-poi')
    expect(result?.feature.properties?.feature_id).toBe('near')
  })

  it('selects a cluster over underlying polygons when no point POI is present', () => {
    const { map } = pickingMap({
      'osm-clusters': [renderedFeature('osm-clusters', { cluster_id: 7 })],
      'overview-polygons-fill': [renderedFeature('overview-polygons-fill', { id: 'polygon' })]
    })
    expect(pickMapEntityAtPoint(map, { x: 20, y: 20 })?.kind).toBe('cluster')
  })

  it('uses the explicit polygon priority instead of rendered-feature order', () => {
    const cityplanner = pickMapEntityAtPoint(pickingMap({
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'area', category: 'retail' })],
      'overview-polygons-fill': [renderedFeature('overview-polygons-fill', { id: 'polygon' })]
    }).map, { x: 20, y: 20 })
    expect(cityplanner?.kind).toBe('interactive-polygon')
    expect(cityplanner?.kind === 'interactive-polygon' && cityplanner.polygon.target).toEqual({ type: 'polygon', id: 'polygon' })

    const osm = pickMapEntityAtPoint(pickingMap({
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'area', category: 'retail' })]
    }).map, { x: 20, y: 20 })
    expect(osm?.kind === 'interactive-polygon' && osm.polygon.selectionKey).toBe('osm-polygons:OSM_POLYGON:area')
  })

  it('queries only explicit custom interactive layers', () => {
    const { map, queryRenderedFeatures } = pickingMap({})
    expect(pickMapEntityAtPoint(map, { x: 20, y: 20 })).toBeNull()
    const queriedLayers = queryRenderedFeatures.mock.calls.flatMap(call => call[1]?.layers || [])
    expect(new Set(queriedLayers)).toEqual(new Set(Object.values(MAP_INTERACTIVE_LAYERS).flat()))
    expect(queriedLayers.some(layer => layer.startsWith('basemap'))).toBe(false)
  })
})
