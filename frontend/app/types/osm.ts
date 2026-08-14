export type OsmFeatureCategory =
  | 'public_transport' | 'parking' | 'gastronomy' | 'retail' | 'groceries'
  | 'education' | 'health' | 'culture' | 'leisure' | 'finance'
  | 'government' | 'hotels' | 'services' | 'tourism' | 'public'
  | 'building' | 'landuse'

export type OsmGeometry =
  | { type: 'Point', coordinates: [number, number] }
  | { type: 'Polygon', coordinates: number[][][] }
  | { type: 'MultiPolygon', coordinates: number[][][][] }

export type OsmViewportFeature = {
  type: 'Feature'
  id: string
  geometry: OsmGeometry
  properties: {
    feature_id: string
    osm_type: 'node' | 'way' | 'relation'
    osm_id: number
    category: OsmFeatureCategory
    name: string | null
    primary_type: string | null
    feature_type: 'point' | 'polygon'
    occupancy_status: 'VACANT' | 'UNKNOWN'
    occupancy_source: 'OSM' | null
    stadtplaner: Array<{ id: string, slug: string, name: string, floor?: string | null }>
  }
}

export type OsmViewportResult = {
  type: 'FeatureCollection'
  features: OsmViewportFeature[]
  meta: {
    count: number
    truncated: boolean
    zoom: number
    summary: Partial<Record<OsmFeatureCategory, number>>
    osm_data_updated_at: string | null
  }
}

export type OsmAddress = {
  street?: string | null
  house_number?: string | null
  postal_code?: string | null
  city?: string | null
}

export type OsmObjectInfo = {
  osm_id: number
  osm_type: 'node' | 'way' | 'relation'
  name?: string | null
  category?: string | null
  shop?: string | null
  amenity?: string | null
  office?: string | null
  craft?: string | null
  tourism?: string | null
  leisure?: string | null
  building?: string | null
  building_levels?: string | null
  brand?: string | null
  operator?: string | null
  opening_hours?: string | null
  website?: string | null
  phone?: string | null
  email?: string | null
  wheelchair?: string | null
  level?: string | null
  indoor?: string | null
  ref?: string | null
  address?: OsmAddress | null
  centroid?: { longitude: number, latitude: number } | null
  overlap_ratio?: number | null
  tags: Record<string, string>
  occupancy_status: 'VACANT' | 'UNKNOWN'
  occupancy_source?: 'OSM' | null
  occupancy_source_tag?: string | null
  previous_osm_shop_type?: string | null
}

export type OsmImportResult = {
  id: string
  slug: string
  geometry_source: 'osm_feature' | 'containing_osm_area' | 'manual'
  source_osm_type: 'node' | 'way' | 'relation'
  source_osm_id: number
  occupancy_status: 'OCCUPIED' | 'VACANT' | 'UNKNOWN'
  occupancy_source: 'OSM' | 'UNKNOWN'
}

export type OsmFeatureDetail = OsmObjectInfo

export type PolygonOsmInfo = {
  polygon_id: string
  polygon_slug: string
  source: 'local' | 'overpass' | 'none'
  matches: OsmObjectInfo[]
  primary_match?: OsmObjectInfo | null
}

export type OsmBounds = { west: number, south: number, east: number, north: number }
