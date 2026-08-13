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

export const industryColors: Record<IndustryKey, string> = {
  warehouse: '#7a087f',
  fashion: '#154d73',
  food: '#ff3f30',
  electronics: '#0d6b45',
  furniture: '#aaa79a',
  garden: '#8a4d29',
  other: '#8585c8',
  gastronomy: '#ffc20e',
  services: '#ffad72',
  otherAreas: '#9b9b9b'
}

export const industries = [
  { key: 'warehouse', label: 'Warenhaus' },
  { key: 'fashion', label: 'Mode / Bekleidung' },
  { key: 'food', label: 'Nahrungsmittel / Drogerie' },
  { key: 'electronics', label: 'Elektro / Technik' },
  { key: 'furniture', label: 'Einrichtungsbedarf' },
  { key: 'garden', label: 'Garten / Freizeit' },
  { key: 'other', label: 'Sonstige Waren' },
  { key: 'gastronomy', label: 'Gastronomie' },
  { key: 'services', label: 'Einzelhandelsnahe Dienstleister' },
  { key: 'otherAreas', label: 'Sonstige Flächen' }
] as const

export const defaultActiveIndustries = industries.map((industry) => industry.key)
