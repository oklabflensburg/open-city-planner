export type AnalyticsFastFacts = {
  shops: number
  vacancy_rate: number | null
  chain_store_rate: number | null
  centrality_index: number | null
  purchasing_power_index: number | null
  reference_date: string | null
  updated_at: string | null
}

export type CityMetricsVerwaltung = Omit<AnalyticsFastFacts, 'shops'> & {
  source: string | null
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
  prime_rents: {
    unit: string
    period: string | null
    rows: PrimeRentRow[]
  }
}
