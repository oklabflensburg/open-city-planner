import { industries, type IndustryKey } from '~/utils/industries'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'

export type SalesAreaSize = 'S' | 'M' | 'L' | 'XL'
export type FloorGroup = 'UG' | 'EG' | 'OG'
export type GisDataSource = 'STADTPLANNER' | 'OSM'

export const SALES_AREA_SIZE_OPTIONS = [
  { value: 'S', label: 'S', description: 'Fachlich gepflegte Größenklasse S' },
  { value: 'M', label: 'M', description: 'Fachlich gepflegte Größenklasse M' },
  { value: 'L', label: 'L', description: 'Fachlich gepflegte Größenklasse L' },
  { value: 'XL', label: 'XL', description: 'Fachlich gepflegte Größenklasse XL' }
] as const

export const FLOOR_OPTIONS = [
  { value: 'UG', label: 'UG', description: 'Untergeschoss' },
  { value: 'EG', label: 'EG', description: 'Erdgeschoss' },
  { value: 'OG', label: 'OG', description: 'Alle Ober- und Dachgeschosse' }
] as const

export const OCCUPANCY_OPTIONS: ReadonlyArray<{ value: OccupancyStatus, label: string, color: string }> = [
  { value: 'OCCUPIED', label: 'Belegt', color: 'bg-emerald-500' },
  { value: 'VACANT', label: 'Leerstehend', color: 'bg-rose-500' },
  { value: 'UNKNOWN', label: 'Unbekannt', color: 'bg-slate-400' }
]

export const BUSINESS_STRUCTURE_OPTIONS: ReadonlyArray<{ value: BusinessStructure, label: string }> = [
  { value: 'CHAIN', label: 'Filialist', },
  { value: 'INDEPENDENT', label: 'Inhabergeführt' },
  { value: 'UNKNOWN', label: 'Unbekannt' }
]

export const DATA_SOURCE_OPTIONS: ReadonlyArray<{ value: GisDataSource, label: string, description: string }> = [
  { value: 'STADTPLANNER', label: 'Stadtplanner', description: 'Fachlich gepflegte Stadtplanner-Flächen' },
  { value: 'OSM', label: 'OpenStreetMap', description: 'Passende lokale OpenStreetMap-Objekte' }
]

export type GisFilterState = {
  sizes: SalesAreaSize[]
  floors: FloorGroup[]
  categories: IndustryKey[]
  statuses: OccupancyStatus[]
  businessStructures: BusinessStructure[]
  sources: GisDataSource[]
}

export const GIS_FILTER_QUERY_KEYS = [
  'area_sizes', 'floors', 'categories', 'occupancy_statuses', 'business_structures', 'sources'
] as const

function ordered<T extends string>(selected: T[], options: readonly T[]): T[] {
  const valid = new Set(selected)
  return options.filter(value => valid.has(value))
}

function canonical<T extends string>(selected: T[], options: readonly T[]): T[] {
  const values = ordered(selected, options)
  return values.length === options.length ? [] : values
}

export function effectiveGisFilters(filters: GisFilterState): GisFilterState {
  return {
    sizes: canonical(filters.sizes, SALES_AREA_SIZE_OPTIONS.map(item => item.value)),
    floors: canonical(filters.floors, FLOOR_OPTIONS.map(item => item.value)),
    categories: canonical(filters.categories, industries.map(item => item.key)),
    statuses: canonical(filters.statuses, OCCUPANCY_OPTIONS.map(item => item.value)),
    businessStructures: canonical(filters.businessStructures, BUSINESS_STRUCTURE_OPTIONS.map(item => item.value)),
    sources: canonical(filters.sources, DATA_SOURCE_OPTIONS.map(item => item.value))
  }
}

export function gisFilterQuery(filters: GisFilterState): URLSearchParams {
  const effective = effectiveGisFilters(filters)
  const query = new URLSearchParams()
  if (effective.sizes.length) query.set('area_sizes', effective.sizes.join(','))
  if (effective.floors.length) query.set('floors', effective.floors.join(','))
  if (effective.categories.length) query.set('categories', effective.categories.join(','))
  if (effective.statuses.length) query.set('occupancy_statuses', effective.statuses.join(','))
  if (effective.businessStructures.length) query.set('business_structures', effective.businessStructures.join(','))
  if (!filters.sources.length) query.set('sources', 'NONE')
  else if (effective.sources.length) query.set('sources', effective.sources.join(','))
  return query
}

export function gisFilterKey(filters: GisFilterState): string {
  return gisFilterQuery(filters).toString()
}

export function gisFilterUrlQuery(filters: GisFilterState): URLSearchParams {
  const query = new URLSearchParams()
  if (filters.sizes.length) query.set('area_sizes', ordered(filters.sizes, SALES_AREA_SIZE_OPTIONS.map(item => item.value)).join(','))
  if (filters.floors.length) query.set('floors', ordered(filters.floors, FLOOR_OPTIONS.map(item => item.value)).join(','))
  if (filters.categories.length) query.set('categories', ordered(filters.categories, industries.map(item => item.key)).join(','))
  if (filters.statuses.length) query.set('occupancy_statuses', ordered(filters.statuses, OCCUPANCY_OPTIONS.map(item => item.value)).join(','))
  if (filters.businessStructures.length) query.set('business_structures', ordered(filters.businessStructures, BUSINESS_STRUCTURE_OPTIONS.map(item => item.value)).join(','))
  if (!filters.sources.length) query.set('sources', 'NONE')
  else if (filters.sources.length < DATA_SOURCE_OPTIONS.length) {
    query.set('sources', ordered(filters.sources, DATA_SOURCE_OPTIONS.map(item => item.value)).join(','))
  }
  return query
}

export function gisFilterStateKey(filters: GisFilterState): string {
  return gisFilterUrlQuery(filters).toString()
}

function queryValues<T extends string>(value: unknown, allowed: readonly T[]): T[] {
  const raw = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const values = new Set(raw.flatMap(item => String(item).split(',')))
  return allowed.filter(item => values.has(item))
}

export function gisFiltersFromQuery(query: Record<string, unknown>): GisFilterState {
  const sources = queryValues(query.sources, DATA_SOURCE_OPTIONS.map(item => item.value))
  const sourcesExplicitlyEmpty = String(query.sources || '').split(',').includes('NONE')
  return {
    sizes: queryValues(query.area_sizes, SALES_AREA_SIZE_OPTIONS.map(item => item.value)),
    floors: queryValues(query.floors, FLOOR_OPTIONS.map(item => item.value)),
    categories: queryValues(query.categories, industries.map(item => item.key)),
    statuses: queryValues(query.occupancy_statuses, OCCUPANCY_OPTIONS.map(item => item.value)),
    businessStructures: queryValues(query.business_structures, BUSINESS_STRUCTURE_OPTIONS.map(item => item.value)),
    sources: sourcesExplicitlyEmpty ? [] : sources.length ? sources : DATA_SOURCE_OPTIONS.map(item => item.value)
  }
}
