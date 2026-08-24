const timestamp = '2026-08-24T10:00:00Z'
const areaTimestamp = '2026-08-24T09:00:00Z'

const area = {
  id: '11111111-1111-4111-8111-111111111111',
  slug: 'altstadt',
  name: 'Altstadt',
  area_type: 'DISTRICT',
  parent_id: null,
  parent_name: null,
  parent_slug: null,
  area_m2: 1_000_000,
  source: 'OSM',
  source_osm_type: 'relation',
  source_osm_id: 123,
  source_admin_level: 10,
  source_place: null,
  source_updated_at: areaTimestamp,
  updated_at: areaTimestamp,
  child_count: 0,
  external_links: { wikidata: null, wikipedia: null }
}

const metrics = {
  polygon_count: 1,
  occupied_count: 1,
  vacant_count: 0,
  chain_count: 0,
  independent_count: 1,
  total_area_m2: 120,
  average_area_m2: 120,
  median_area_m2: 120,
  vacancy_rate: 0,
  chain_store_rate: 0,
  known_occupancy_count: 1,
  known_business_structure_count: 1,
  data_updated_at: timestamp
}

const polygon = {
  id: '22222222-2222-4222-8222-222222222222',
  slug: 'test-flaeche',
  name: 'Testfläche',
  description: 'Deterministische öffentliche Testfläche.',
  floor: 'EG',
  area_size: 'M',
  address_display_name: 'Teststraße 1, 24937 Flensburg',
  address_lookup_status: 'resolved',
  category: 'food',
  occupancy_status: 'OCCUPIED',
  occupancy_source: 'MANUAL',
  business_structure: 'INDEPENDENT',
  geometry: {
    type: 'Polygon',
    coordinates: [[[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]]
  },
  osm_sources: [],
  external_links: { wikidata: null, wikipedia: null },
  area_m2: 120,
  perimeter_m: 48,
  centroid: [9.4305, 54.7805],
  bbox: [9.43, 54.78, 9.431, 54.781],
  created_at: timestamp,
  updated_at: timestamp
}

export default defineEventHandler((event) => {
  const path = getRequestURL(event).pathname

  if (path === '/api/v1/polygons/sitemap') return [{ slug: polygon.slug, updated_at: polygon.updated_at }]
  if (path === '/api/v1/analysis-areas/sitemap') return [{ slug: area.slug, updated_at: area.updated_at }]
  if (path.includes('does-not-exist')) throw createError({ statusCode: 404, statusMessage: 'Nicht gefunden' })
  if (path === `/api/v1/polygons/by-slug/${polygon.slug}`) return polygon
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}`) {
    return {
      ...area,
      parent: null,
      municipality: null,
      children: [],
      geometry: {
        type: 'MultiPolygon',
        coordinates: [[[[9.42, 54.77], [9.44, 54.77], [9.44, 54.79], [9.42, 54.77]]]]
      },
      centroid: [9.43, 54.78],
      bbox: [9.42, 54.77, 9.44, 54.79]
    }
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/analytics`) {
    return { area, metrics, industry_distribution: [], poi_count: 0, poi_categories: [], retail_area_density_m2_per_km2: 120 }
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/comparison`) {
    return { area, municipality: area, area_metrics: metrics, municipality_metrics: metrics, differences: [] }
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/polygons`) return []
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/statistics`) {
    const reference = { id: area.id, slug: area.slug, name: area.name, area_type: area.area_type }
    return { area: reference, statistics_area: reference, inherited_from_parent: false, source: null, latest: [] }
  }
  if (path === '/api/v1/analysis-areas') return []
  if (path === '/api/v1/analysis-areas/geojson') return { type: 'FeatureCollection', features: [] }
  if (path === '/api/v1/polygons/overview') return []
  if (path === '/api/v1/analytics/overview') {
    return {
      fast_facts: {
        shops: 0, polygon_count: 0, total_area_m2: null, average_area_m2: null,
        median_area_m2: null, vacant_area_m2: null, vacancy_area_rate: null,
        calculated_vacancy_rate: null, calculated_chain_store_rate: null,
        known_occupancy_count: 0, known_business_structure_count: 0,
        data_updated_at: null, vacancy_rate: null, chain_store_rate: null,
        centrality_index: null, purchasing_power_index: null, reference_date: null,
        source: null, updated_at: null
      },
      industry_distribution: [], category_counts: [], size_distribution: [],
      floor_distribution: [], status_distribution: [], business_structure_distribution: [],
      data_completeness: [], prime_rents: { unit: 'EUR_PER_SQM', period: null, rows: [] }
    }
  }
  if (path === '/api/v1/osm/features') {
    return {
      type: 'FeatureCollection', features: [],
      meta: {
        count: 0, summary: {}, canonical_summary: {}, canonical_facets: {}, business_count: 0,
        context_count: 0, deduplicated_linked_count: 0, truncated: false, zoom: 16,
        osm_data_updated_at: null
      }
    }
  }

  throw createError({ statusCode: 404, statusMessage: 'Fixture nicht definiert' })
})
