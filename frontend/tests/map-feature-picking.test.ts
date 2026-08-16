import type { Map, MapGeoJSONFeature } from 'maplibre-gl'
import { describe, expect, it, vi } from 'vitest'
import { MAP_INTERACTIVE_LAYERS, pickMapEntityAtPoint } from '~/utils/mapFeaturePicking'

function renderedFeature(layerId: string, properties: Record<string, unknown>, coordinates: [number, number] = [20, 20]) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates },
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

  it('falls back through OSM polygon, Stadtplanner polygon and analysis area', () => {
    expect(pickMapEntityAtPoint(pickingMap({
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'area', category: 'retail' })],
      'overview-polygons-fill': [renderedFeature('overview-polygons-fill', { id: 'polygon' })]
    }).map, { x: 20, y: 20 })?.kind).toBe('osm-poi-polygon')

    expect(pickMapEntityAtPoint(pickingMap({
      'overview-polygons-fill': [renderedFeature('overview-polygons-fill', { id: 'polygon' })],
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'landuse', category: 'landuse' })],
      'analysis-areas-quarter-fill': [renderedFeature('analysis-areas-quarter-fill', { id: 'quarter' })]
    }).map, { x: 20, y: 20 })?.kind).toBe('cityplanner-polygon')

    expect(pickMapEntityAtPoint(pickingMap({
      'osm-polygons-fill': [renderedFeature('osm-polygons-fill', { feature_id: 'landuse', category: 'landuse' })],
      'analysis-areas-quarter-fill': [renderedFeature('analysis-areas-quarter-fill', { id: 'quarter' })]
    }).map, { x: 20, y: 20 })?.kind).toBe('osm-context-polygon')

    expect(pickMapEntityAtPoint(pickingMap({
      'analysis-areas-quarter-fill': [renderedFeature('analysis-areas-quarter-fill', { id: 'quarter' })]
    }).map, { x: 20, y: 20 })?.kind).toBe('analysis-area')
  })

  it('queries only explicit custom interactive layers', () => {
    const { map, queryRenderedFeatures } = pickingMap({})
    expect(pickMapEntityAtPoint(map, { x: 20, y: 20 })).toBeNull()
    const queriedLayers = queryRenderedFeatures.mock.calls.flatMap(call => call[1]?.layers || [])
    expect(new Set(queriedLayers)).toEqual(new Set(Object.values(MAP_INTERACTIVE_LAYERS).flat()))
    expect(queriedLayers.some(layer => layer.startsWith('basemap'))).toBe(false)
  })
})
