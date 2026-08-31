/** Read-only consumer projection of the external Analysis Areas HTTP API. */
export type PublicAreaType = 'MUNICIPALITY' | 'DISTRICT' | 'QUARTER'

export type PublicAreaReference = {
  id: string
  slug: string
  name: string
  area_type: PublicAreaType
  parent_id: string | null
  parent_name: string | null
  parent_slug: string | null
  area_m2: number
  source: 'OSM' | 'MANUAL'
  source_osm_type: string | null
  source_osm_id: number | null
  source_admin_level: number | null
  source_place: string | null
  source_updated_at: string | null
  updated_at: string
  child_count: number
  external_links: ExternalLinks
}

export type ExternalLinks = {
  wikidata: { id: string, url: string } | null
  wikipedia: { title: string, url: string } | null
}

export type PublicAreaSitemapEntry = {
  slug: string
  updated_at: string
}
