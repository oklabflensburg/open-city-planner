import { createServer } from 'node:http'
import { SEO_AUDIT_POLYGON_SLUG } from './seo-route-matrix.mjs'

const timestamp = '2026-08-24T10:00:00Z'
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
  external_links: { wikipedia: null },
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
        district_slug: null,
        district_name: null,
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
  if (path === `/api/v1/polygons/by-slug/${polygon.slug}`) return ok(polygon)
  if (path.startsWith('/api/v1/polygons/by-slug/')) return notFound('Die Fläche wurde nicht gefunden.')
  return notFound('SEO-Audit-Fixture nicht definiert.')
}

function ok(body) {
  return { status: 200, body }
}

function notFound(message) {
  return { status: 404, body: { detail: message } }
}
