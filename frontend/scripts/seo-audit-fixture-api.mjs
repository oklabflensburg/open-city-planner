import { createServer } from 'node:http'
import { SEO_AUDIT_AREA_SLUG, SEO_AUDIT_POLYGON_SLUG } from './seo-route-matrix.mjs'

const timestamp = '2026-08-24T10:00:00Z'
const areaTimestamp = '2026-08-24T09:00:00Z'
const areaId = '11111111-1111-4111-8111-111111111111'

const area = {
  id: areaId,
  slug: SEO_AUDIT_AREA_SLUG,
  name: 'Audit-Altstadt',
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
  slug: SEO_AUDIT_POLYGON_SLUG,
  name: 'Audit-Testfläche',
  description: 'Deterministische öffentliche Audit-Fläche.',
  floor: 'EG',
  area_size: 'M',
  address_display_name: 'Teststraße 1, 24937 Flensburg',
  address_street: 'Teststraße',
  address_house_number: '1',
  address_postal_code: '24937',
  address_city: 'Flensburg',
  address_country: 'Deutschland',
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

export async function startSeoAuditFixtureApi() {
  const server = createServer((request, response) => {
    const url = new URL(request.url || '/', 'http://fixture.invalid')
    const result = fixtureResponse(url.pathname)
    response.writeHead(result.status, {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store'
    })
    response.end(JSON.stringify(result.body))
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('SEO fixture API did not bind to TCP')
  return {
    baseUrl: `http://127.0.0.1:${address.port}/api/v1`,
    close: () => new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  }
}

function fixtureResponse(path) {
  if (path === '/api/v1/polygons/sitemap') return ok([{ slug: polygon.slug, updated_at: polygon.updated_at }])
  if (path === '/api/v1/analysis-areas/sitemap') return ok([{ slug: area.slug, updated_at: area.updated_at }])
  if (path === '/api/v1/polygons/directory') {
    return ok({
      items: [{
        slug: polygon.slug,
        name: polygon.name,
        category: polygon.category,
        floor: polygon.floor,
        address_display_name: polygon.address_display_name,
        occupancy_status: polygon.occupancy_status,
        business_structure: polygon.business_structure,
        district_slug: area.slug,
        district_name: area.name,
        quarter_slug: null,
        quarter_name: null,
        updated_at: polygon.updated_at
      }],
      total: 1,
      offset: 0,
      limit: 250,
      next_offset: null
    })
  }
  if (path === '/api/v1/analysis-areas') return ok([area])
  if (path === `/api/v1/polygons/by-slug/${polygon.slug}`) return ok(polygon)
  if (path.startsWith('/api/v1/polygons/by-slug/')) return notFound('Die Fläche wurde nicht gefunden.')
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}`) {
    return ok({
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
    })
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/analytics`) {
    return ok({ area, metrics, industry_distribution: [], poi_count: 0, poi_categories: [], retail_area_density_m2_per_km2: 120 })
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/comparison`) {
    return ok({ area, municipality: area, area_metrics: metrics, municipality_metrics: metrics, differences: [] })
  }
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/polygons`) return ok([])
  if (path === `/api/v1/analysis-areas/by-slug/${area.slug}/statistics`) {
    const reference = { id: area.id, slug: area.slug, name: area.name, area_type: area.area_type }
    return ok({ area: reference, statistics_area: reference, inherited_from_parent: false, source: null, latest: [] })
  }
  if (path.startsWith('/api/v1/analysis-areas/by-slug/')) return notFound('Das Gebiet wurde nicht gefunden.')
  return notFound('SEO-Audit-Fixture nicht definiert.')
}

function ok(body) {
  return { status: 200, body }
}

function notFound(message) {
  return { status: 404, body: { detail: message } }
}
