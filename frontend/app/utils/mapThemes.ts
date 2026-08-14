export type MapTheme = 'category' | 'occupancy' | 'size' | 'business'

export const mapThemes: Array<{ key: MapTheme, label: string }> = [
  { key: 'category', label: 'Branchen' },
  { key: 'occupancy', label: 'Leerstand' },
  { key: 'size', label: 'Flächengröße' },
  { key: 'business', label: 'Filialisierung' }
]

export const occupancyLegend = [
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

export const businessLegend = [
  { value: 'CHAIN', label: 'Filialist', color: '#7c3aed' },
  { value: 'INDEPENDENT', label: 'Inhabergeführt', color: '#f59e0b' },
  { value: 'UNKNOWN', label: 'Unbekannt', color: '#94a3b8' }
]
