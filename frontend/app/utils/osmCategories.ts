import type { OsmFeatureCategory } from '~/types/osm'

export const osmPoiCategories: Array<{ key: OsmFeatureCategory, label: string, color: string }> = [
  { key: 'retail', label: 'Einzelhandel', color: '#2563eb' },
  { key: 'groceries', label: 'Lebensmittel', color: '#16a34a' },
  { key: 'gastronomy', label: 'Gastronomie', color: '#ea580c' },
  { key: 'services', label: 'Dienstleistungen', color: '#7c3aed' },
  { key: 'public_transport', label: 'ÖPNV', color: '#0891b2' },
  { key: 'parking', label: 'Parken', color: '#64748b' },
  { key: 'education', label: 'Bildung', color: '#ca8a04' },
  { key: 'health', label: 'Gesundheit', color: '#dc2626' },
  { key: 'culture', label: 'Kultur', color: '#db2777' },
  { key: 'leisure', label: 'Freizeit', color: '#059669' },
  { key: 'finance', label: 'Banken', color: '#4f46e5' },
  { key: 'government', label: 'Behörden', color: '#475569' },
  { key: 'hotels', label: 'Hotels', color: '#9333ea' },
  { key: 'tourism', label: 'Tourismus', color: '#0d9488' },
  { key: 'public', label: 'Öffentliche Einrichtungen', color: '#78716c' }
]

export const osmCategoryColors = Object.fromEntries(osmPoiCategories.map(item => [item.key, item.color]))
export const osmCategoryLabels = Object.fromEntries([
  ...osmPoiCategories.map(item => [item.key, item.label]),
  ['building', 'Gebäude'], ['landuse', 'Flächennutzung']
]) as Record<OsmFeatureCategory, string>

export function osmColorExpression() {
  return ['match', ['get', 'category'], ...Object.entries(osmCategoryColors).flat(), '#64748b']
}
