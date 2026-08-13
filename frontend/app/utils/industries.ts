export type IndustryKey =
  | 'warehouse'
  | 'fashion'
  | 'food'
  | 'electronics'
  | 'furniture'
  | 'garden'
  | 'other'
  | 'gastronomy'
  | 'services'
  | 'otherAreas'

export type IndustryConfig = {
  key: IndustryKey
  label: string
  color: string
}

export const fallbackIndustryColor = '#64748b'

export const industries: readonly IndustryConfig[] = [
  { key: 'warehouse', label: 'Warenhaus', color: '#7a087f' },
  { key: 'fashion', label: 'Mode / Bekleidung', color: '#154d73' },
  { key: 'food', label: 'Nahrungsmittel / Drogerie', color: '#ff3f30' },
  { key: 'electronics', label: 'Elektro / Technik', color: '#0d6b45' },
  { key: 'furniture', label: 'Einrichtungsbedarf', color: '#77756c' },
  { key: 'garden', label: 'Garten / Freizeit', color: '#8a4d29' },
  { key: 'other', label: 'Sonstige Waren', color: '#6b6bb0' },
  { key: 'gastronomy', label: 'Gastronomie', color: '#b77900' },
  { key: 'services', label: 'Einzelhandelsnahe Dienstleister', color: '#c45f22' },
  { key: 'otherAreas', label: 'Sonstige Flächen', color: '#64748b' }
]

export const industryColors = Object.fromEntries(
  industries.map(industry => [industry.key, industry.color])
) as Record<IndustryKey, string>

export function getIndustry(category: string | null | undefined) {
  return industries.find(industry => industry.key === category)
}

export function getIndustryLabel(category: string | null | undefined) {
  return getIndustry(category)?.label || category || 'Nicht angegeben'
}

export function getIndustryColor(category: string | null | undefined) {
  return getIndustry(category)?.color || fallbackIndustryColor
}

export function industryColorExpression(property = 'category') {
  return [
    'match',
    ['get', property],
    ...Object.entries(industryColors).flat(),
    fallbackIndustryColor
  ]
}

export function colorWithAlpha(hex: string, alpha: number) {
  const normalized = hex.replace('#', '')
  if (!/^[0-9a-f]{6}$/i.test(normalized)) return `rgb(100 116 139 / ${alpha})`
  const value = Number.parseInt(normalized, 16)
  return `rgb(${value >> 16} ${(value >> 8) & 255} ${value & 255} / ${alpha})`
}

export const defaultActiveIndustries = industries.map((industry) => industry.key)
