import type { UserPolygon } from '~/types/geo'
import { getIndustryLabel } from '~/utils/industries'

export type PolygonSort =
  | 'updated-desc'
  | 'created-desc'
  | 'created-asc'
  | 'name-asc'
  | 'name-desc'
  | 'category-asc'

export const defaultPolygonSort: PolygonSort = 'updated-desc'

export const polygonSortOptions: ReadonlyArray<{ value: PolygonSort, label: string }> = [
  { value: 'updated-desc', label: 'Zuletzt aktualisiert' },
  { value: 'created-desc', label: 'Neueste zuerst' },
  { value: 'created-asc', label: 'Älteste zuerst' },
  { value: 'name-asc', label: 'Name A–Z' },
  { value: 'name-desc', label: 'Name Z–A' },
  { value: 'category-asc', label: 'Kategorie A–Z' }
]

export function isPolygonSort(value: unknown): value is PolygonSort {
  return polygonSortOptions.some(option => option.value === value)
}

export function normalizePolygonSearchValue(value: unknown) {
  return String(value ?? '')
    .trim()
    .toLocaleLowerCase('de-DE')
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function searchablePropertyValues(properties: Record<string, unknown>) {
  return Object.values(properties).filter(value =>
    typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
  )
}

function timestamp(value: string) {
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

const germanCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true })

export function filterAndSortPolygons(
  polygons: readonly UserPolygon[],
  search: string,
  category: string,
  sort: PolygonSort
) {
  const needle = normalizePolygonSearchValue(search)
  const result = polygons.filter((polygon) => {
    if (category && polygon.category !== category) return false
    if (!needle) return true
    const searchable = [
      polygon.name,
      polygon.category,
      getIndustryLabel(polygon.category),
      polygon.slug,
      polygon.description,
      polygon.floor,
      ...searchablePropertyValues(polygon.properties)
    ].map(normalizePolygonSearchValue).join(' ')
    return searchable.includes(needle)
  })

  return result.sort((left, right) => {
    if (sort === 'created-desc') return timestamp(right.created_at) - timestamp(left.created_at)
    if (sort === 'created-asc') return timestamp(left.created_at) - timestamp(right.created_at)
    if (sort === 'name-asc') return germanCollator.compare(left.name, right.name)
    if (sort === 'name-desc') return germanCollator.compare(right.name, left.name)
    if (sort === 'category-asc') {
      return germanCollator.compare(getIndustryLabel(left.category), getIndustryLabel(right.category))
        || germanCollator.compare(left.name, right.name)
    }
    return timestamp(right.updated_at) - timestamp(left.updated_at)
  })
}
