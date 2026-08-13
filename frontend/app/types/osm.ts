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
}

export type PolygonOsmInfo = {
  polygon_id: string
  polygon_slug: string
  source: 'local' | 'overpass' | 'none'
  matches: OsmObjectInfo[]
  primary_match?: OsmObjectInfo | null
}
