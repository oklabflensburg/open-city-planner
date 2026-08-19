import { industries, type IndustryKey } from '~/utils/industries'
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'
import { occupancyLegend } from '~/utils/mapThemes'

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

export const OCCUPANCY_OPTIONS = occupancyLegend

export const BUSINESS_STRUCTURE_OPTIONS: ReadonlyArray<{ value: BusinessStructure, label: string }> = [
  { value: 'CHAIN', label: 'Filialist', },
  { value: 'INDEPENDENT', label: 'Inhabergeführt' },
  { value: 'UNKNOWN', label: 'Unbekannt' }
]

export const DATA_SOURCE_OPTIONS: ReadonlyArray<{ value: GisDataSource, label: string, description: string }> = [
  { value: 'STADTPLANNER', label: 'Stadtplaner', description: 'Fachlich gepflegte Stadtplaner-Flächen' },
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

export function defaultGisFilters(): GisFilterState {
  return {
    sizes: SALES_AREA_SIZE_OPTIONS.map(item => item.value),
    floors: FLOOR_OPTIONS.map(item => item.value),
    categories: industries.map(item => item.key),
    statuses: OCCUPANCY_OPTIONS.map(item => item.value),
    businessStructures: BUSINESS_STRUCTURE_OPTIONS.map(item => item.value),
    sources: DATA_SOURCE_OPTIONS.map(item => item.value)
  }
}

function ordered<T extends string>(selected: T[], options: readonly T[]): T[] {
  const valid = new Set(selected)
  return options.filter(value => valid.has(value))
}

export function requiredFacetSelection<T extends string>(
  current: T[],
  next: T[],
  options: readonly T[]
): T[] {
  const selected = ordered(next, options)
  if (selected.length) return selected
  const previous = ordered(current, options)
  return previous.length ? previous : [...options]
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
  setDimension(query, 'area_sizes', filters.sizes, effective.sizes)
  setDimension(query, 'floors', filters.floors, effective.floors)
  setDimension(query, 'categories', filters.categories, effective.categories)
  setDimension(query, 'occupancy_statuses', filters.statuses, effective.statuses)
  setDimension(query, 'business_structures', filters.businessStructures, effective.businessStructures)
  setDimension(query, 'sources', filters.sources, effective.sources)
  return query
}

export function gisFilterKey(filters: GisFilterState): string {
  return gisFilterQuery(filters).toString()
}

export function gisFilterUrlQuery(filters: GisFilterState): URLSearchParams {
  return gisFilterQuery(filters)
}

export function gisFilterStateKey(filters: GisFilterState): string {
  return gisFilterUrlQuery(filters).toString()
}

function queryValues<T extends string>(value: unknown, allowed: readonly T[]): T[] {
  const raw = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const values = new Set(raw.flatMap(item => String(item).split(',')))
  return allowed.filter(item => values.has(item))
}

function setDimension<T extends string>(query: URLSearchParams, key: string, selected: T[], effective: T[]) {
  if (!selected.length) query.set(key, 'NONE')
  else if (effective.length) query.set(key, effective.join(','))
}

function queryDimension<T extends string>(query: Record<string, unknown>, key: string, allowed: readonly T[]): T[] {
  const raw = query[key]
  if (raw === undefined || raw === null || raw === '') return [...allowed]
  if ((Array.isArray(raw) ? raw : [raw]).flatMap(item => String(item).split(',')).includes('NONE')) return []
  return queryValues(raw, allowed)
}

function requiredQueryDimension<T extends string>(query: Record<string, unknown>, key: string, allowed: readonly T[]): T[] {
  const selected = queryDimension(query, key, allowed)
  return selected.length ? selected : [...allowed]
}

export function gisFiltersFromQuery(query: Record<string, unknown>): GisFilterState {
  return {
    sizes: requiredQueryDimension(query, 'area_sizes', SALES_AREA_SIZE_OPTIONS.map(item => item.value)),
    floors: requiredQueryDimension(query, 'floors', FLOOR_OPTIONS.map(item => item.value)),
    categories: requiredQueryDimension(query, 'categories', industries.map(item => item.key)),
    statuses: requiredQueryDimension(query, 'occupancy_statuses', OCCUPANCY_OPTIONS.map(item => item.value)),
    businessStructures: requiredQueryDimension(query, 'business_structures', BUSINESS_STRUCTURE_OPTIONS.map(item => item.value)),
    sources: queryDimension(query, 'sources', DATA_SOURCE_OPTIONS.map(item => item.value))
  }
}
