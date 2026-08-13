import type { OsmAddress, OsmObjectInfo } from '~/types/osm'

const labels: Record<string, string> = {
  'shop=clothes': 'Mode / Bekleidung',
  'shop=supermarket': 'Supermarkt',
  'shop=bakery': 'Bäckerei',
  'shop=shoes': 'Schuhgeschäft',
  'shop=department_store': 'Warenhaus',
  'amenity=restaurant': 'Restaurant',
  'amenity=cafe': 'Café',
  'amenity=pharmacy': 'Apotheke',
  'amenity=bank': 'Bank',
  'tourism=hotel': 'Hotel'
}

const categoryKeys = ['shop', 'amenity', 'office', 'craft', 'tourism', 'leisure', 'building'] as const

export function osmCategoryRaw(object: OsmObjectInfo) {
  const key = categoryKeys.find(candidate => object[candidate])
  return key ? `${key}=${object[key]}` : null
}

export function osmCategoryLabel(object: OsmObjectInfo) {
  const raw = osmCategoryRaw(object)
  return raw ? labels[raw] || raw : 'Nicht kategorisiert'
}

export function osmObjectUrl(object: OsmObjectInfo) {
  return `https://www.openstreetmap.org/${object.osm_type}/${object.osm_id}`
}

export function safeOsmWebsite(value?: string | null) {
  if (!value) return null
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : null
  } catch {
    return null
  }
}

export function formatOsmAddress(address?: OsmAddress | null) {
  if (!address) return null
  return [
    [address.street, address.house_number].filter(Boolean).join(' '),
    [address.postal_code, address.city].filter(Boolean).join(' ')
  ].filter(Boolean).join(', ') || null
}
