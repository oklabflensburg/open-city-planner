import { describe, expect, it } from 'vitest'
import { shouldExcludeOsmFeature } from '~/utils/osmExclusions'
import type { OsmViewportFeature } from '~/types/osm'

function feature(natural?: string): OsmViewportFeature {
  return {
    type: 'Feature', id: 'way/1', geometry: { type: 'Polygon', coordinates: [] },
    properties: {
      feature_id: 'way/1', osm_type: 'way', osm_id: 1, category: 'landuse',
      name: null, primary_type: natural || null, natural, feature_type: 'polygon',
      source: 'OSM', canonical_category: null, canonical_floor: null, mapped_area_m2: null,
      occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: [],
      external_links: { wikidata: null, wikipedia: null }
    }
  }
}

describe('OSM exclusion policy', () => {
  it('excludes only natural=peninsula from the interactive overlay', () => {
    expect(shouldExcludeOsmFeature(feature('peninsula'))).toBe(true)
    expect(shouldExcludeOsmFeature(feature('wood'))).toBe(false)
    expect(shouldExcludeOsmFeature(feature('water'))).toBe(false)
    expect(shouldExcludeOsmFeature(feature())).toBe(false)
  })
})
