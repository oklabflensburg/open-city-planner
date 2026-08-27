import type { Map } from 'maplibre-gl'

export const MAP_LAYER_GROUPS = {
  analysisAreas: [
    'analysis-areas.municipality-fill',
    'analysis-areas.district-fill',
    'analysis-areas.quarter-fill',
    'analysis-areas.municipality',
    'analysis-areas.district',
    'analysis-areas.quarter',
    'analysis-areas.municipality-label',
    'analysis-areas.district-label',
    'analysis-areas.quarter-label'
  ],
  osmPolygons: [
    'osm-polygons-fill',
    'osm-polygons-line'
  ],
  cityplannerPolygons: [
    'overview-polygons-fill',
    'overview-polygons-line'
  ],
  polygonHighlights: [
    'selected-polygon-fill',
    'selected-polygon-halo',
    'selected-polygon-outline'
  ],
  poiClusters: [
    'osm-clusters',
    'osm-cluster-count'
  ],
  pois: [
    'osm-poi-circle',
    'osm-selected-point-halo',
    'osm-selected-point'
  ],
  poiLabels: [
    'osm-poi-label'
  ]
} as const

export const MAP_LAYER_ORDER = Object.values(MAP_LAYER_GROUPS).flat()

type LayerOrderMap = Pick<Map, 'getLayer' | 'getStyle' | 'moveLayer'>

export function getStadtplanerLayerOrder(map: Pick<Map, 'getStyle'>) {
  const customLayerIds = new Set<string>(MAP_LAYER_ORDER)
  return map.getStyle().layers.map(layer => layer.id).filter(id => customLayerIds.has(id))
}

export function hasValidStadtplanerLayerOrder(map: Pick<Map, 'getStyle'>) {
  const actual = getStadtplanerLayerOrder(map)
  const expected = MAP_LAYER_ORDER.filter(id => actual.includes(id))
  return actual.every((id, index) => id === expected[index])
}

export function ensureStadtplanerLayerOrder(map: LayerOrderMap) {
  if (hasValidStadtplanerLayerOrder(map)) return

  let beforeId: string | undefined
  for (const layerId of [...MAP_LAYER_ORDER].reverse()) {
    if (!map.getLayer(layerId)) continue
    map.moveLayer(layerId, beforeId)
    beforeId = layerId
  }
}
