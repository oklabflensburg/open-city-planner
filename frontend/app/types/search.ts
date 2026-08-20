import type { FeatureCollection } from 'geojson'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'
import type { AnalysisAreaType } from '~/types/analysisArea'
import type { FloorGroup, GisDataSource, SalesAreaSize } from '~/utils/gisFilters'
import type { IndustryKey } from '~/utils/industries'

export type SearchIntent = 'SHOW_AREA' | 'SHOW_ANALYSIS_AREAS' | 'SHOW_FEATURES' | 'CHANGE_FILTERS' | 'COUNT_FEATURES' | 'ASK_ANALYTICS' | 'COMPARE_AREA'
export type SearchMapActionType = 'NONE' | 'FIT_AREA' | 'SHOW_ANALYSIS_AREAS' | 'REPLACE_SEARCH_LAYER' | 'UPDATE_FILTERS'
export type SearchGeometryFilter = 'ALL' | 'POINTS_ONLY' | 'POLYGONS_ONLY'

export type SearchFilters = {
  categories: IndustryKey[]
  occupancy_statuses: OccupancyStatus[]
  floors: FloorGroup[]
  area_sizes: SalesAreaSize[]
  business_structures: BusinessStructure[]
  sources: GisDataSource[]
}

export type SearchPlan = {
  intent: SearchIntent
  area: { id: string, name: string, slug: string, area_type: AnalysisAreaType } | null
  area_type: AnalysisAreaType | null
  filters: SearchFilters
  geometry_filter: SearchGeometryFilter
  osm_amenities?: string[]
  map_action: { type: SearchMapActionType, fit_bounds: boolean }
}

export type SearchResponse = {
  query: string
  plan: SearchPlan
  answer: string
  map_action: {
    type: SearchMapActionType
    fit_bounds: boolean
    bounds: [number, number, number, number] | null
  }
  data: FeatureCollection | Record<string, unknown> | null
  warnings: string[]
  error_code: string | null
}

export function isFeatureCollection(value: unknown): value is FeatureCollection {
  return Boolean(value && typeof value === 'object'
    && (value as { type?: string }).type === 'FeatureCollection'
    && Array.isArray((value as { features?: unknown }).features))
}

export type AssistantIntent = 'ANSWER_QUESTION' | 'COMPARE_AREAS' | 'SHOW_FEATURES' | 'CHANGE_FILTERS' | 'LIST_AREAS' | 'UNSUPPORTED'
export type AnswerPresentationType = 'TEXT' | 'METRIC' | 'METRIC_LIST' | 'COMPARISON' | 'AREA_LIST' | 'FEATURE_LIST' | 'KNOWLEDGE' | 'DATA_SOURCE_STATUS' | 'STATISTICS_OVERVIEW' | 'STATISTIC_SERIES' | 'STATISTIC_METRIC'
export type AssistantMapActionType = 'FIT_AREA' | 'SHOW_ANALYSIS_AREAS' | 'HIGHLIGHT_AREAS' | 'REPLACE_SEARCH_LAYER' | 'UPDATE_FILTERS'

export type AssistantContext = {
  active_area: SearchPlan['area']
  active_filters: SearchFilters
  last_compared_areas: NonNullable<SearchPlan['area']>[]
  last_intent: AssistantIntent | null
  last_topic: string | null
  last_metric_key?: string | null
  last_source_type?: string | null
  selected_polygon_slug: string | null
  selected_osm_feature: { osm_type: 'node' | 'way' | 'relation', osm_id: number } | null
  viewport: { west: number, south: number, east: number, north: number, zoom: number } | null
}

export type AssistantMapAction = {
  type: AssistantMapActionType
  area_slug: string | null
  area_slugs: string[]
  area_type: AnalysisAreaType | null
  fit_bounds: boolean
  bounds: [number, number, number, number] | null
  feature_collection: FeatureCollection | null
  filters: SearchFilters | null
  geometry_filter: SearchGeometryFilter | null
}

export type AssistantPresentation = {
  type: AnswerPresentationType
  title: string
  value: number | string | null
  unit: string | null
  items: Record<string, unknown>[]
  metadata?: Record<string, unknown>
  sections?: AssistantPresentation[]
}

export type AssistantResponse = {
  query: string
  answer: string
  plan: { intent: AssistantIntent, steps: { tool: string, arguments: Record<string, unknown> }[], response_mode: 'ANSWER' | 'CLARIFICATION' | 'REFUSAL' }
  presentation: AssistantPresentation
  citations: { type: string, slug: string | null, source: string | null, period: string | null, inherited_from_parent: boolean | null }[]
  sources_used: { type: string, area_slug: string | null, updated_at: string | null, source: string | null, period: string | null, inherited_from_parent: boolean | null, knowledge_key: string | null }[]
  map_actions: AssistantMapAction[]
  context: AssistantContext
  warnings: string[]
  claims: { text: string, evidence: { type: string, field: string | null, area_slug: string | null, knowledge_key: string | null, osm_type: string | null, osm_id: number | null }[] }[]
  follow_up_actions: { type: 'SHOW_ON_MAP' | 'COMPARE_WITH_AREA' | 'EXPLAIN_CONCEPT' | 'SHOW_STATISTICS' | 'SHOW_DATA_SOURCE', label: string, query: string }[]
  presentation_behavior?: 'KEEP_OPEN' | 'AUTO_CLOSE' | 'COLLAPSE'
  telemetry: { llm_used: boolean, model: string | null, tool_calls: number, duration_ms: number, intent: AssistantIntent, success: boolean, provider: string | null, prompt_version: string | null, knowledge_version: string | null, tool_registry_version: string | null, input_tokens: number | null, output_tokens: number | null, total_tokens: number | null }
}
