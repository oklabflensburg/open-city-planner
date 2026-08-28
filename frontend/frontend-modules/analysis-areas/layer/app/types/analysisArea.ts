type Position = [number, number]
type MultiPolygon = { type: 'MultiPolygon', coordinates: Position[][][] }
type FeatureCollection<G, P> = {
  type: 'FeatureCollection'
  features: Array<{ type: 'Feature', id?: string | number, geometry: G, properties: P }>
}

export type BenchmarkMetrics = {
  polygon_count: number
  occupied_count: number
  vacant_count: number
  chain_count: number
  independent_count: number
  total_area_m2: number | null
  average_area_m2: number | null
  median_area_m2: number | null
  vacancy_rate: number | null
  chain_store_rate: number | null
  known_occupancy_count: number
  known_business_structure_count: number
  data_updated_at: string | null
}

export type IndustryCount = { category: string, count: number }

export type AnalysisAreaType = 'MUNICIPALITY' | 'DISTRICT' | 'QUARTER'

export type AnalysisArea = {
  id: string
  slug: string
  name: string
  area_type: AnalysisAreaType
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
  external_links: {
    wikidata: { id: string, url: string } | null
    wikipedia: { title: string, url: string } | null
  }
}

export type AnalysisAreaReference = Pick<AnalysisArea, 'id' | 'slug' | 'name' | 'area_type'>

export type AnalysisAreaDetail = AnalysisArea & {
  parent: AnalysisAreaReference | null
  municipality: AnalysisAreaReference | null
  children: AnalysisAreaReference[]
  geometry: MultiPolygon
  centroid: [number, number]
  bbox: [number, number, number, number]
}

export type AnalysisAreaPolygon = {
  id: string
  slug: string
  name: string
  category: string
  floor: string | null
  address_display_name: string | null
  occupancy_status: 'OCCUPIED' | 'VACANT' | 'UNKNOWN'
  area_m2: number | null
}

export type AnalysisAreaSitemapEntry = {
  slug: string
  updated_at: string
}

export type AnalysisAreaFeatureCollection = FeatureCollection<MultiPolygon, {
  id: string, name: string, slug: string, area_type: AnalysisAreaType, parent_id: number | null,
  area_m2: number, source: string, source_osm_type: string | null, source_osm_id: number | null,
  source_admin_level: number | null
}>

export type AnalysisAreaAnalytics = {
  area: AnalysisArea
  metrics: BenchmarkMetrics
  industry_distribution: IndustryCount[]
  poi_count: number
  poi_categories: IndustryCount[]
  retail_area_density_m2_per_km2: number | null
}

export type AnalysisAreaComparison = {
  area: AnalysisArea
  municipality: AnalysisArea
  area_metrics: BenchmarkMetrics
  municipality_metrics: BenchmarkMetrics
  differences: Array<{ key: string, area_value: number | null, municipality_value: number | null, difference: number | null, unit: string }>
}

export type StatisticsSource = {
  name: string
  url: string
  license: string
  source_updated_at: string | null
  last_import_at: string | null
}

export type AreaStatisticValue = {
  key: string
  name: string
  category: string
  value: number | string | null
  unit: string
  period: string
  period_start: string
  area_level: AnalysisAreaType
  is_calculated: boolean
  municipality_value: number | string | null
  difference: number | string | null
  relative_difference: number | string | null
}

export type AreaStatistics = {
  area: AnalysisAreaReference
  statistics_area: AnalysisAreaReference
  inherited_from_parent: boolean
  source: StatisticsSource | null
  latest: AreaStatisticValue[]
}

export type AreaStatisticSeries = {
  area: AnalysisAreaReference
  statistics_area: AnalysisAreaReference
  inherited_from_parent: boolean
  source: StatisticsSource | null
  metric: { key: string, name: string, unit: string, category: string }
  series: Array<{ period: string, period_start: string, value: number | string | null, suppressed: boolean }>
}
