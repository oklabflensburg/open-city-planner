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
  { key: 'warehouse', label: 'Warenhaus', value: 7 },
  { key: 'fashion', label: 'Mode/Bekleidung', value: 34 },
  { key: 'food', label: 'Nahrungsmittel/Drogerie', value: 12 },
  { key: 'electronics', label: 'Elektro, Technik', value: 2 },
  { key: 'furniture', label: 'Einrichtungsbedarf', value: 3 },
  { key: 'garden', label: 'Garten/Freizeit', value: 1 },
  { key: 'other', label: 'Sonstige Waren', value: 14 },
  { key: 'gastronomy', label: 'Gastronomie', value: 8 },
  { key: 'services', label: 'Einzelhandelsnahe Dienstleister', value: 10 },
  { key: 'otherAreas', label: 'Sonstige Flächen', value: 5 }
] as const

export const defaultActiveIndustries = industries.map((industry) => industry.key)

