import type { GeoJsonProperties, Geometry } from 'geojson'
import type { Map, MapGeoJSONFeature, PointLike } from 'maplibre-gl'

export type InteractivePolygonTarget =
  | { type: 'polygon', id: string }
  | { type: 'osm', id: string }
  | { type: 'module', id: string }

export type InteractivePolygonFeature = {
  id: string
  source: string
  sourceLayer?: string
  layerId: string
  featureType: string
  geometryType: 'Polygon' | 'MultiPolygon'
  selectionKey: string
  geometry: Geometry
  properties: GeoJsonProperties
  target: InteractivePolygonTarget
}

type InteractivePolygonRegistration = {
  layerId: string
  source: string
  featureType: string
  idProperty: string
  priority: number
  targetType: InteractivePolygonTarget['type']
}

/** Single source of truth for selectable polygon layers and deterministic overlap priority. */
export const INTERACTIVE_POLYGON_LAYERS: readonly InteractivePolygonRegistration[] = [
  { layerId: 'overview-polygons-fill', source: 'overview-polygons', featureType: 'STADTPLANNER', idProperty: 'id', priority: 500, targetType: 'polygon' },
  { layerId: 'osm-polygons-fill', source: 'osm-polygons', featureType: 'OSM_POLYGON', idProperty: 'feature_id', priority: 400, targetType: 'osm' },
] as const

export const MAP_INTERACTIVE_LAYERS = {
  pointPois: ['osm-poi-circle'],
  clusters: ['osm-clusters'],
  polygons: INTERACTIVE_POLYGON_LAYERS.map(item => item.layerId)
} as const

export type MapPickResult =
  | { kind: 'point-poi' | 'cluster', feature: MapGeoJSONFeature }
  | { kind: 'interactive-polygon', feature: MapGeoJSONFeature, polygon: InteractivePolygonFeature }

type FeaturePickingMap = Pick<Map, 'getLayer' | 'project' | 'queryRenderedFeatures'>
type ScreenPoint = { x: number, y: number }

export function pickMapEntityAtPoint(map: FeaturePickingMap, point: ScreenPoint, tolerance = 8): MapPickResult | null {
  const box: [[number, number], [number, number]] = [
    [point.x - tolerance, point.y - tolerance],
    [point.x + tolerance, point.y + tolerance]
  ]
  const pointPoi = closestPointFeature(map, point, queryExistingLayers(map, box, MAP_INTERACTIVE_LAYERS.pointPois))
  if (pointPoi) return { kind: 'point-poi', feature: pointPoi }

  const cluster = closestPointFeature(map, point, queryExistingLayers(map, box, MAP_INTERACTIVE_LAYERS.clusters))
  if (cluster) return { kind: 'cluster', feature: cluster }

  const registrations = new globalThis.Map(INTERACTIVE_POLYGON_LAYERS.map(item => [item.layerId, item] as const))
  const candidates = queryExistingLayers(map, [point.x, point.y], MAP_INTERACTIVE_LAYERS.polygons)
    .map((feature) => {
      const registration = registrations.get(feature.layer.id)
      const polygon = registration ? normalizeInteractivePolygon(feature, registration) : null
      const contextPenalty = registration?.source === 'osm-polygons' && isContextPolygon(feature) ? 150 : 0
      return polygon && registration ? { feature, polygon, priority: registration.priority - contextPenalty } : null
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .sort((left, right) => right.priority - left.priority)

  const selected = candidates[0]
  return selected ? { kind: 'interactive-polygon', feature: selected.feature, polygon: selected.polygon } : null
}

function normalizeInteractivePolygon(
  feature: MapGeoJSONFeature,
  registration: InteractivePolygonRegistration
): InteractivePolygonFeature | null {
  if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') return null
  const id = String(feature.properties?.[registration.idProperty] ?? feature.id ?? '')
  if (!id) return null
  const featureType = registration.source === 'osm-polygons' && isContextPolygon(feature)
      ? 'OSM_CONTEXT_POLYGON'
      : registration.featureType
  return {
    id,
    source: registration.source,
    sourceLayer: feature.sourceLayer,
    layerId: registration.layerId,
    featureType,
    geometryType: feature.geometry.type,
    selectionKey: `${registration.source}:${featureType}:${id}`,
    geometry: feature.geometry,
    properties: feature.properties,
    target: { type: registration.targetType, id } as InteractivePolygonTarget
  }
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
