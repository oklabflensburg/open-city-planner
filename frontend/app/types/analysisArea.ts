import type { FeatureCollection, MultiPolygon } from 'geojson'
import type { BenchmarkMetrics, IndustryCount } from '~/types/analytics'

export type AnalysisAreaType = 'MUNICIPALITY' | 'DISTRICT' | 'QUARTER'

export type AnalysisArea = {
  id: string
  slug: string
  name: string
  area_type: AnalysisAreaType
  parent_id: string | null
  parent_name: string | null
  area_m2: number
  source: 'OSM' | 'MANUAL'
  source_osm_type: string | null
  source_osm_id: number | null
  source_admin_level: number | null
  source_place: string | null
  source_updated_at: string | null
  child_count: number
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
