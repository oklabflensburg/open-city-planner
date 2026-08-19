import type { OsmAddress, OsmObjectInfo } from '~/types/osm'
import { formatOsmCategory } from '~/utils/osmTranslations'

export function osmCategoryLabel(object: OsmObjectInfo) {
  return formatOsmCategory(osmObjectTags(object)).value
}

export function osmObjectTags(object: OsmObjectInfo): Record<string, string> {
  const tags = { ...object.tags }
  for (const key of ['shop', 'amenity', 'office', 'craft', 'tourism', 'leisure', 'building'] as const) {
    if (object[key] && !tags[key]) tags[key] = object[key]
  }
  return tags
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
