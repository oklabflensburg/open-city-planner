import type { Map, MapGeoJSONFeature, PointLike } from 'maplibre-gl'

export const MAP_INTERACTIVE_LAYERS = {
  pointPois: ['osm-poi-circle'],
  clusters: ['osm-clusters'],
  osmPolygons: ['osm-polygons-fill'],
  cityplannerPolygons: ['overview-polygons-fill'],
  analysisAreas: [
    'analysis-areas-quarter-fill',
    'analysis-areas-district-fill',
    'analysis-areas-municipality-fill'
  ]
} as const

export type MapPickResult = {
  kind: 'point-poi' | 'cluster' | 'osm-poi-polygon' | 'cityplanner-polygon' | 'osm-context-polygon' | 'analysis-area'
  feature: MapGeoJSONFeature
}

type FeaturePickingMap = Pick<Map, 'getLayer' | 'project' | 'queryRenderedFeatures'>
type ScreenPoint = { x: number, y: number }

export function pickMapEntityAtPoint(map: FeaturePickingMap, point: ScreenPoint, tolerance = 8): MapPickResult | null {
  const exactPoint: [number, number] = [point.x, point.y]
  const box: [[number, number], [number, number]] = [
    [point.x - tolerance, point.y - tolerance],
    [point.x + tolerance, point.y + tolerance]
  ]
  const pointPoi = closestPointFeature(map, point, queryExistingLayers(map, box, MAP_INTERACTIVE_LAYERS.pointPois))
  if (pointPoi) return { kind: 'point-poi', feature: pointPoi }

  const cluster = closestPointFeature(map, point, queryExistingLayers(map, box, MAP_INTERACTIVE_LAYERS.clusters))
  if (cluster) return { kind: 'cluster', feature: cluster }

  const osmPolygonHits = queryExistingLayers(map, exactPoint, MAP_INTERACTIVE_LAYERS.osmPolygons)
  const osmPoiPolygon = osmPolygonHits.find(feature => !isContextPolygon(feature))
  if (osmPoiPolygon) return { kind: 'osm-poi-polygon', feature: osmPoiPolygon }

  const cityplannerPolygon = queryExistingLayers(map, exactPoint, MAP_INTERACTIVE_LAYERS.cityplannerPolygons)[0]
  if (cityplannerPolygon) return { kind: 'cityplanner-polygon', feature: cityplannerPolygon }

  const osmContextPolygon = osmPolygonHits.find(isContextPolygon)
  if (osmContextPolygon) return { kind: 'osm-context-polygon', feature: osmContextPolygon }

  const analysisHits = queryExistingLayers(map, exactPoint, MAP_INTERACTIVE_LAYERS.analysisAreas)
  const analysisArea = MAP_INTERACTIVE_LAYERS.analysisAreas
    .map(layerId => analysisHits.find(feature => feature.layer.id === layerId))
    .find((feature): feature is MapGeoJSONFeature => Boolean(feature))
  return analysisArea ? { kind: 'analysis-area', feature: analysisArea } : null
}

function isContextPolygon(feature: MapGeoJSONFeature) {
  return feature.properties?.category === 'landuse' || feature.properties?.category === 'building'
}

function queryExistingLayers(
  map: FeaturePickingMap,
  geometry: PointLike | [PointLike, PointLike],
  layerIds: readonly string[]
) {
  const layers = layerIds.filter(layerId => map.getLayer(layerId))
  return layers.length ? map.queryRenderedFeatures(geometry, { layers }) : []
}

function closestPointFeature(map: FeaturePickingMap, point: ScreenPoint, features: MapGeoJSONFeature[]) {
  return features.reduce<MapGeoJSONFeature | null>((closest, feature) => {
    if (!closest) return feature
    return screenDistance(map, point, feature) < screenDistance(map, point, closest) ? feature : closest
  }, null)
}

function screenDistance(map: FeaturePickingMap, point: ScreenPoint, feature: MapGeoJSONFeature) {
  if (feature.geometry.type !== 'Point') return Number.POSITIVE_INFINITY
  const projected = map.project(feature.geometry.coordinates as [number, number])
  return Math.hypot(projected.x - point.x, projected.y - point.y)
}
