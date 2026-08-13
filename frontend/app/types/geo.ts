export type Position = [number, number]

export type PolygonGeometry = {
  type: 'Polygon'
  coordinates: Position[][]
}

export type PolygonProperties = Record<string, unknown> & {
  name?: string
  category?: string
}

export type PolygonFeature = {
  type: 'Feature'
  id?: string
  geometry: PolygonGeometry
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
  geometry: PolygonGeometry
  properties: Record<string, unknown>
  created_by_user_id?: string | null
  updated_by_user_id?: string | null
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
  geometry: PolygonGeometry
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
  geometry: PolygonGeometry
  created_at: string
  updated_at: string
} & PolygonMetrics

export type PolygonEditorDetail = PublicPolygonDetail & {
  can_edit_public_fields: boolean
}

export type PolygonVerwaltungDetail = PublicPolygonDetail & {
  owner_name?: string | null
  owner_street?: string | null
  owner_house_number?: string | null
  owner_postal_code?: string | null
  owner_city?: string | null
  owner_country?: string | null
  price_per_sqm?: string | null
  created_by_user_id?: string | null
  updated_by_user_id?: string | null
}

export type PolygonSitemapEntry = {
  slug: string
  updated_at: string
}
