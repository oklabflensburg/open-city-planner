import industryConfig from '~/config/industries.json'

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

export const fallbackIndustryColor = '#789098'

export const industries = industryConfig as readonly IndustryConfig[]

export const industryColors = Object.fromEntries(
  industries.map(industry => [industry.key, industry.color])
) as Record<IndustryKey, string>

export function getIndustry(category: string | null | undefined) {
  return industries.find(industry => industry.key === category)
}

const additionalIndustryLabels: Readonly<Record<string, string>> = {
  custom: 'Benutzerdefinierte Fläche'
}

function humanizeIndustryKey(category: string) {
  const value = category
    .trim()
    .replace(/([a-z\d])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
  if (!value) return 'Nicht angegeben'
  return value.charAt(0).toLocaleUpperCase('de-DE') + value.slice(1)
}

export function getIndustryLabel(category: string | null | undefined) {
  if (!category?.trim()) return 'Nicht angegeben'
  return getIndustry(category)?.label
    || additionalIndustryLabels[category]
    || humanizeIndustryKey(category)
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
