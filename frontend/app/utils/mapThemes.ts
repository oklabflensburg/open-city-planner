import type { BusinessStructure, OccupancyStatus } from '~/types/geo'
import { getIndustryColor, industryColorExpression } from '~/utils/industries'

export type MapTheme = 'category' | 'occupancy' | 'size' | 'business'

export const mapThemes: Array<{ key: MapTheme, label: string }> = [
  { key: 'category', label: 'Branchen' },
  { key: 'occupancy', label: 'Leerstand' },
  { key: 'size', label: 'Flächengröße' },
  { key: 'business', label: 'Filialisierung' }
]

export const occupancyLegend: ReadonlyArray<{ value: OccupancyStatus, label: string, color: string }> = [
  { value: 'OCCUPIED', label: 'Belegt', color: '#10b981' },
  { value: 'VACANT', label: 'Leerstehend', color: '#f43f5e' },
  { value: 'UNKNOWN', label: 'Unbekannt', color: '#94a3b8' }
]

export const sizeLegend = [
  { value: 'S', label: 'S', color: '#dbeafe' },
  { value: 'M', label: 'M', color: '#93c5fd' },
  { value: 'L', label: 'L', color: '#3b82f6' },
  { value: 'XL', label: 'XL', color: '#1e3a8a' }
]

export const businessLegend: ReadonlyArray<{ value: BusinessStructure, label: string, color: string }> = [
  { value: 'CHAIN', label: 'Filialist', color: '#7c3aed' },
  { value: 'INDEPENDENT', label: 'Inhabergeführt', color: '#f59e0b' },
  { value: 'UNKNOWN', label: 'Unbekannt', color: '#94a3b8' }
]

const colorByValue = (items: ReadonlyArray<{ value: string, color: string }>) =>
  Object.fromEntries(items.map(item => [item.value, item.color])) as Record<string, string>

export const occupancyColors = colorByValue(occupancyLegend) as Record<OccupancyStatus, string>
export const sizeColors = colorByValue(sizeLegend)
export const businessColors = colorByValue(businessLegend) as Record<BusinessStructure, string>

type ThemeProperties = {
  category?: unknown
  occupancy_status?: unknown
  size?: unknown
  business_structure?: unknown
}

export function thematicColor(theme: MapTheme, properties: ThemeProperties): string {
  if (theme === 'occupancy') {
    return occupancyColors[String(properties.occupancy_status) as OccupancyStatus] || occupancyColors.UNKNOWN
  }
  if (theme === 'size') return sizeColors[String(properties.size)] || '#94a3b8'
  if (theme === 'business') {
    return businessColors[String(properties.business_structure) as BusinessStructure] || businessColors.UNKNOWN
  }
  return getIndustryColor(String(properties.category || ''))
}

export function thematicColorExpression(theme: MapTheme): unknown[] {
  if (theme === 'occupancy') {
    return ['match', ['get', 'occupancy_status'],
      'OCCUPIED', occupancyColors.OCCUPIED,
      'VACANT', occupancyColors.VACANT,
      occupancyColors.UNKNOWN]
  }
  if (theme === 'size') {
    return ['match', ['get', 'size'],
      'S', sizeColors.S,
      'M', sizeColors.M,
      'L', sizeColors.L,
      'XL', sizeColors.XL,
      '#94a3b8']
  }
  if (theme === 'business') {
    return ['match', ['get', 'business_structure'],
      'CHAIN', businessColors.CHAIN,
      'INDEPENDENT', businessColors.INDEPENDENT,
      businessColors.UNKNOWN]
  }
  return industryColorExpression()
}
