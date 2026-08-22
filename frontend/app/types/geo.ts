export type Position = [number, number]

export type PolygonGeometry = {
  type: 'Polygon'
  coordinates: Position[][]
}

export type MultiPolygonGeometry = {
  type: 'MultiPolygon'
  coordinates: Position[][][]
}

export type AreaGeometry = PolygonGeometry | MultiPolygonGeometry

export type PolygonProperties = Record<string, unknown> & {
  name?: string
  category?: string
}

export type PolygonFeature = {
  type: 'Feature'
  id?: string
  geometry: AreaGeometry
  properties: PolygonProperties
}

export type PolygonFeatureCollection = {
  type: 'FeatureCollection'
  features: PolygonFeature[]
}

export type UserPolygon = {
  id: string
  slug: string
  name: string
  description?: string | null
  floor?: string | null
  category: string
  geometry: AreaGeometry
  properties: Record<string, unknown>
  created_by_user_id?: string | null
  updated_by_user_id?: string | null
  created_at: string
  updated_at: string
}

export type PublicPolygonRead = {
  id: string
  slug: string
  name: string
  description?: string | null
  floor?: string | null
  category: string
  geometry: AreaGeometry
  properties: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PolygonOverview = {
  id: string
  slug: string
  name: string
  category: string
  floor?: string | null
  area_size?: string | null
  address_display_name?: string | null
  occupancy_status: OccupancyStatus
  business_structure: BusinessStructure
  geometry: AreaGeometry
  created_at: string
  updated_at: string
}

export type PolygonMetrics = {
  area_m2: number
  perimeter_m: number
  centroid: Position
  bbox: [number, number, number, number]
}

export type PublicPolygonDetail = {
  id: string
  slug: string
  name: string
  description?: string | null
  floor?: string | null
  area_size?: 'S' | 'M' | 'L' | 'XL' | null
  address_display_name?: string | null
  address_street?: string | null
  address_house_number?: string | null
  address_postal_code?: string | null
  address_city?: string | null
  address_country?: string | null
  address_lookup_status: 'pending' | 'resolved' | 'failed'
  category: string
  occupancy_status: OccupancyStatus
  occupancy_source: 'OSM' | 'MANUAL' | 'IMPORTED' | 'CALCULATED' | 'UNKNOWN'
  business_structure: BusinessStructure
  geometry: AreaGeometry
  osm_sources: PolygonOsmSource[]
  external_links: import('~/types/osm').ExternalLinks
  created_at: string
  updated_at: string
} & PolygonMetrics

export type PolygonEditorDetail = PublicPolygonDetail & {
  can_edit_public_fields: boolean
  can_delete: boolean
}

export type OccupancyStatus = 'OCCUPIED' | 'VACANT' | 'UNKNOWN'
export type BusinessStructure = 'CHAIN' | 'INDEPENDENT' | 'UNKNOWN'

export type PolygonVerwaltungDetail = PublicPolygonDetail & {
  owner_name?: string | null
  owner_street?: string | null
  owner_house_number?: string | null
  owner_postal_code?: string | null
  owner_city?: string | null
  owner_country?: string | null
  price_per_sqm?: string | null
  occupancy_source_tag?: string | null
  occupancy_source_updated_at?: string | null
  created_by_user_id?: string | null
  updated_by_user_id?: string | null
}

export type PolygonOsmSource = {
  osm_type: 'node' | 'way' | 'relation'
  osm_id: number
  is_primary: boolean
  imported_at: string
  external_links: import('~/types/osm').ExternalLinks
}

export type PolygonSitemapEntry = {
  slug: string
  updated_at: string
}
