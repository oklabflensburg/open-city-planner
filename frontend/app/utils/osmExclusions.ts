import type { OsmViewportFeature } from '~/types/osm'

export function shouldExcludeOsmFeature(feature: OsmViewportFeature) {
  return feature.properties.natural?.trim().toLowerCase() === 'peninsula'
}
