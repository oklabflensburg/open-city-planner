import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 90_000 })

const rings = {
  municipality: [[[9.426, 54.776], [9.444, 54.776], [9.444, 54.790], [9.426, 54.790], [9.426, 54.776]]],
  district: [[[9.429, 54.779], [9.442, 54.779], [9.442, 54.788], [9.429, 54.788], [9.429, 54.779]]],
  quarter: [[[9.431, 54.781], [9.440, 54.781], [9.440, 54.786], [9.431, 54.786], [9.431, 54.781]]]
}

const areaRows = [
  ['municipality', 'MUNICIPALITY', 'Testgemeinde', null],
  ['district', 'DISTRICT', 'Teststadtteil', 'municipality'],
  ['quarter', 'QUARTER', 'Testquartier', 'district']
].map(([id, area_type, name, parent_id]) => ({
  id, slug: id, name, area_type, parent_id, parent_name: null, parent_slug: null,
  area_m2: 1_000_000, source: 'OSM', source_osm_type: 'relation', source_osm_id: 1,
  source_admin_level: 6, source_place: null, source_updated_at: null,
  updated_at: '2026-08-17T08:00:00Z', child_count: 0,
  external_links: { wikidata: null, wikipedia: null }
}))

const areaGeojson = {
  type: 'FeatureCollection',
  features: areaRows.map(area => ({
    type: 'Feature', id: area.id,
    geometry: { type: 'MultiPolygon', coordinates: [rings[area.id as keyof typeof rings]] },
    properties: { id: area.id, name: area.name, slug: area.slug, area_type: area.area_type, parent_id: area.parent_id }
  }))
}

const cityPolygon = {
  id: '44444444-4444-4444-8444-444444444444', slug: 'browser-testflaeche', name: 'Browser-Testfläche',
  category: 'fashion', floor: 'EG', area_size: 'S', address_display_name: 'Flensburg',
  occupancy_status: 'OCCUPIED', business_structure: 'INDEPENDENT',
  geometry: { type: 'Polygon', coordinates: [[[9.4301, 54.7801], [9.4309, 54.7801], [9.4309, 54.7807], [9.4301, 54.7801]]] },
  created_at: '2026-08-17T08:00:00Z', updated_at: '2026-08-17T08:00:00Z'
}

const osmPolygon = {
  type: 'Feature', id: 'way/123',
  geometry: { type: 'Polygon', coordinates: [[[9.4378, 54.7837], [9.4388, 54.7837], [9.4388, 54.7845], [9.4378, 54.7837]]] },
  properties: {
    feature_id: 'way/123', osm_type: 'way', osm_id: 123, category: 'retail', canonical_category: 'fashion',
    name: 'OSM-Testfläche', primary_type: 'clothes', natural: null, feature_type: 'polygon', source: 'OSM',
    canonical_floor: 'EG', mapped_area_m2: 80, occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: []
  }
}

async function mockMapData(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/polygons/overview**', route => route.fulfill({ json: [cityPolygon] }))
  await page.route('**/api/v1/analytics/overview**', route => route.fulfill({ json: {
    fast_facts: { shops: 1, polygon_count: 1, total_area_m2: 100, average_area_m2: 100, median_area_m2: 100, vacant_area_m2: 0, vacancy_area_rate: 0, calculated_vacancy_rate: 0, calculated_chain_store_rate: 0, known_occupancy_count: 1, known_business_structure_count: 1, data_updated_at: null, vacancy_rate: null, chain_store_rate: null, centrality_index: null, purchasing_power_index: null, reference_date: null, source: null, updated_at: null },
    industry_distribution: [{ category: 'fashion', count: 1 }], category_counts: [{ category: 'fashion', count: 1 }], prime_rents: { unit: 'EUR_PER_SQM', period: null, rows: [] }
  } }))
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection', features: [osmPolygon],
    meta: { count: 1, summary: { retail: 1 }, canonical_summary: { fashion: 1 }, canonical_facets: { fashion: 1 }, business_count: 1, context_count: 0, deduplicated_linked_count: 0, truncated: false, zoom: 16, osm_data_updated_at: null }
  } }))
  await page.route('**/api/v1/osm/features/way/123', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
  await page.route('**/api/v1/analysis-areas**', (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/geojson')) return route.fulfill({ json: areaGeojson })
    if (path.endsWith('/analysis-areas')) return route.fulfill({ json: areaRows })
    return route.fulfill({ status: 500, json: { detail: 'not needed' } })
  })
  await page.route('**/api/v1/polygons/44444444-4444-4444-8444-444444444444/metrics', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
  await page.route('**/api/v1/polygons/by-slug/browser-testflaeche/osm', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
}

async function clickCoordinate(page: Page, coordinate: [number, number], zoom: number) {
  const point = await page.evaluate(async ({ coordinate, zoom }) => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance!.map
    map.jumpTo({ center: coordinate, zoom })
    await new Promise<void>(resolve => map.once('idle', () => resolve()))
    const projected = map.project(coordinate)
    const bounds = map.getCanvas().getBoundingClientRect()
    return {
      x: bounds.left + projected.x,
      y: bounds.top + projected.y,
      layers: map.queryRenderedFeatures(projected, { layers: ['overview-polygons-fill', 'osm-polygons-fill', 'analysis-areas-quarter-fill', 'analysis-areas-district-fill', 'analysis-areas-municipality-fill'].filter(id => map.getLayer(id)) }).map(feature => feature.layer.id)
    }
  }, { coordinate, zoom })
  await page.mouse.click(point.x, point.y)
  return point.layers
}

async function expectUniversalSelection(page: Page, featureType: string) {
  await expect.poll(() => page.evaluate(() => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance!.map
    const features = map.querySourceFeatures('selected-polygon-source')
    return { count: new Set(features.map(feature => feature.properties?.selection_key)).size, type: features[0]?.properties?.feature_type }
  })).toEqual({ count: 1, type: featureType })
}

test('one universal overlay selects every interactive polygon type and clears cleanly', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockMapData(page)
  await page.goto('/')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('1 Stadtplaner · 1 OSM im Ausschnitt')).toBeVisible({ timeout: 20_000 })

  const canvas = page.locator('.maplibregl-canvas')
  await expect(canvas).toHaveCSS('cursor', 'grab')
  const hoverPoint = await page.evaluate(async () => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance!.map
    map.jumpTo({ center: [9.4305, 54.78035], zoom: 16.4 })
    await new Promise<void>(resolve => map.once('idle', () => resolve()))
    const point = map.project([9.4305, 54.78035])
    const bounds = map.getCanvas().getBoundingClientRect()
    return { x: bounds.left + point.x, y: bounds.top + point.y }
  })
  await page.mouse.move(hoverPoint.x, hoverPoint.y)
  await expect(canvas).toHaveCSS('cursor', 'pointer')

  const bounds = await canvas.boundingBox()
  if (!bounds) throw new Error('Map canvas has no bounding box')
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width / 2 + 60, bounds.y + bounds.height / 2 + 30, { steps: 4 })
  await expect(canvas).toHaveCSS('cursor', 'grabbing')
  await page.mouse.up()
  await expect(canvas).toHaveCSS('cursor', 'grab')

  expect(await clickCoordinate(page, [9.4305, 54.78035], 16.4)).toContain('overview-polygons-fill')
  await expectUniversalSelection(page, 'STADTPLANNER')
  await expect(page.getByText('Browser-Testfläche', { exact: true })).toBeVisible()

  await clickCoordinate(page, [9.43825, 54.784], 16.4)
  await expectUniversalSelection(page, 'OSM_POLYGON')
  await expect(page.getByText('OSM-Testfläche', { exact: true })).toBeVisible()

  await clickCoordinate(page, [9.432, 54.782], 14)
  await expectUniversalSelection(page, 'QUARTER')
  await expect(page.getByText('Testquartier', { exact: true })).toBeVisible()

  await clickCoordinate(page, [9.430, 54.787], 12)
  await expectUniversalSelection(page, 'DISTRICT')
  await expect(page.getByText('Teststadtteil', { exact: true })).toBeVisible()

  await clickCoordinate(page, [9.427, 54.777], 9)
  await expectUniversalSelection(page, 'MUNICIPALITY')
  await expect(page.getByText('Testgemeinde', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Gebietsauswahl schließen' }).click()
  await expect.poll(() => page.evaluate(() => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance!.map
    return map.querySourceFeatures('selected-polygon-source').length
  })).toBe(0)
})
