import type { Map } from 'maplibre-gl'
import { describe, expect, it, vi } from 'vitest'
import { MAP_LAYER_GROUPS, MAP_LAYER_ORDER, ensureStadtplanerLayerOrder, getStadtplanerLayerOrder, hasValidStadtplanerLayerOrder } from '~/utils/mapLayerOrder'

function layerMap(initialLayerIds: string[]) {
  const layerIds = [...initialLayerIds]
  const map = {
    getLayer: (id: string) => layerIds.includes(id) ? { id } : undefined,
    getStyle: () => ({ layers: layerIds.map(id => ({ id })) }),
    moveLayer: vi.fn((id: string, beforeId?: string) => {
      layerIds.splice(layerIds.indexOf(id), 1)
      const target = beforeId ? layerIds.indexOf(beforeId) : layerIds.length
      layerIds.splice(target, 0, id)
    })
  } as unknown as Pick<Map, 'getLayer' | 'getStyle' | 'moveLayer'>
  return { map, layerIds }
}

describe('Stadtplaner MapLibre layer order', () => {
  it('places every polygon layer below clusters, POIs and POI labels', () => {
    const scrambled = [
      'basemap-label',
      ...MAP_LAYER_GROUPS.pois,
      ...MAP_LAYER_GROUPS.analysisAreas,
      ...MAP_LAYER_GROUPS.poiLabels,
      ...MAP_LAYER_GROUPS.cityplannerPolygons,
      ...MAP_LAYER_GROUPS.poiClusters,
      ...MAP_LAYER_GROUPS.osmPolygons,
      ...MAP_LAYER_GROUPS.polygonHighlights
    ]
    const { map } = layerMap(scrambled)

    ensureStadtplanerLayerOrder(map)

    expect(getStadtplanerLayerOrder(map)).toEqual(MAP_LAYER_ORDER)
    expect(hasValidStadtplanerLayerOrder(map)).toBe(true)
    const order = getStadtplanerLayerOrder(map)
    const polygonIds = [
      ...MAP_LAYER_GROUPS.analysisAreas,
      ...MAP_LAYER_GROUPS.osmPolygons,
      ...MAP_LAYER_GROUPS.cityplannerPolygons,
      ...MAP_LAYER_GROUPS.polygonHighlights
    ]
    const poiIds = [...MAP_LAYER_GROUPS.poiClusters, ...MAP_LAYER_GROUPS.pois, ...MAP_LAYER_GROUPS.poiLabels]
    expect(Math.max(...polygonIds.map(id => order.indexOf(id)))).toBeLessThan(Math.min(...poiIds.map(id => order.indexOf(id))))
  })

  it('restores the same order after a style reload and tolerates missing optional layers', () => {
    const { map, layerIds } = layerMap(['basemap', 'osm-poi-circle', 'overview-polygons-fill'])
    ensureStadtplanerLayerOrder(map)
    expect(getStadtplanerLayerOrder(map)).toEqual(['overview-polygons-fill', 'osm-poi-circle'])

    layerIds.splice(0, layerIds.length, 'new-basemap', 'osm-poi-label', 'osm-polygons-fill', 'osm-clusters')
    ensureStadtplanerLayerOrder(map)

    expect(getStadtplanerLayerOrder(map)).toEqual(['osm-polygons-fill', 'osm-clusters', 'osm-poi-label'])
  })

  it('does no layer movement when the custom order is already valid', () => {
    const { map } = layerMap(['basemap', ...MAP_LAYER_ORDER])
    ensureStadtplanerLayerOrder(map)
    expect(map.moveLayer).not.toHaveBeenCalled()
  })
})
