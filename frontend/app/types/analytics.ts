export type AnalyticsFastFacts = {
  shops: number
  polygon_count: number
  total_area_m2: number | null
  average_area_m2: number | null
  median_area_m2: number | null
  vacant_area_m2: number | null
  vacancy_area_rate: number | null
  calculated_vacancy_rate: number | null
  calculated_chain_store_rate: number | null
  known_occupancy_count: number
  known_business_structure_count: number
  data_updated_at: string | null
  vacancy_rate: number | null
  chain_store_rate: number | null
  centrality_index: number | null
  purchasing_power_index: number | null
  reference_date: string | null
  source: string | null
  updated_at: string | null
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

export type MarketBenchmarkResult = {
  context_label: string
  calculation: 'CALCULATED'
  source: string
  items: Array<{ key: string, label: string, metrics: BenchmarkMetrics }>
}

export type AreaCompareMetrics = {
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
  locations_per_km2: number | null
  retail_area_m2_per_km2: number | null
}

export type AreaCompareItem = {
  id: string
  slug: string
  name: string
  area_type: 'MUNICIPALITY' | 'DISTRICT' | 'QUARTER'
  parent_name: string | null
  area_m2: number
  metrics: AreaCompareMetrics
}

export type AreaCompareResult = {
  areas: AreaCompareItem[]
  benchmark: AreaCompareItem | null
  ignored_slugs: string[]
  calculation: 'CALCULATED'
  source: string
}

export type PoiSummary = { category: string, label: string, count: number }
export type LocationAnalysis = {
  polygon_slug: string
  radius_m: number
  poi_counts: PoiSummary[]
  nearest_public_transport: { category: string, label: string, name: string | null, distance_m: number } | null
  source: string
  reference_date: string | null
}

export type ComparablePolygon = {
  slug: string
  title: string
  distance_m: number
  area_m2: number
  category: string
  floor: string | null
  similarity_score: number
}

export type ComparableResult = { polygon_slug: string, calculation: 'CALCULATED', items: ComparablePolygon[] }

export type CityMetricsVerwaltung = {
  vacancy_rate: number | null
  chain_store_rate: number | null
  centrality_index: number | null
  purchasing_power_index: number | null
  reference_date: string | null
  source: string | null
  updated_at: string | null
  notes: string | null
  updated_by_user_id: string | null
}

export type CityMetricsUpdate = Partial<Pick<CityMetricsVerwaltung,
  'vacancy_rate' | 'chain_store_rate' | 'centrality_index' | 'purchasing_power_index' | 'reference_date' | 'source' | 'notes'
>>

export type IndustryCount = {
  category: string
  count: number
}

export type DimensionCount = { key: string, label: string, count: number }
export type CompletenessMetric = { key: string, label: string, complete: number, total: number, percent: number | null }

export type PrimeRentRow = {
  location: string
  s: number | null
  m: number | null
  l: number | null
  xl: number | null
}

export type AnalyticsOverview = {
  fast_facts: AnalyticsFastFacts
  industry_distribution: IndustryCount[]
  category_counts: IndustryCount[]
  size_distribution: DimensionCount[]
  floor_distribution: DimensionCount[]
  status_distribution: DimensionCount[]
  business_structure_distribution: DimensionCount[]
  data_completeness: CompletenessMetric[]
  prime_rents: {
    unit: string
    period: string | null
    rows: PrimeRentRow[]
  }
}
