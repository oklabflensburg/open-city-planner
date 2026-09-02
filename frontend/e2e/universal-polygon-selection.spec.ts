import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 90_000 })

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
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection', features: [osmPolygon],
    meta: { count: 1, summary: { retail: 1 }, canonical_summary: { fashion: 1 }, canonical_facets: { fashion: 1 }, business_count: 1, context_count: 0, deduplicated_linked_count: 0, truncated: false, zoom: 16, osm_data_updated_at: null }
  } }))
  await page.route('**/api/v1/osm/features/way/123', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
  await page.route('**/api/v1/polygons/44444444-4444-4444-8444-444444444444/metrics', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
  await page.route('**/api/v1/polygons/by-slug/browser-testflaeche/osm', route => route.fulfill({ status: 500, json: { detail: 'not needed' } }))
}

async function clickCoordinate(page: Page, coordinate: [number, number]) {
  const point = await page.evaluate(async (coordinate) => {
    const map = window.__stadtplanerMapPerformance!.map
    map.jumpTo({ center: coordinate, zoom: 16.4 })
    await new Promise<void>(resolve => map.once('idle', () => resolve()))
    const projected = map.project(coordinate)
    const bounds = map.getCanvas().getBoundingClientRect()
    return { x: bounds.left + projected.x, y: bounds.top + projected.y }
  }, coordinate)
  await page.mouse.click(point.x, point.y)
}

async function expectSelection(page: Page, featureType: string) {
  await expect.poll(() => page.evaluate(() => {
    const features = window.__stadtplanerMapPerformance!.map.querySourceFeatures('selected-polygon-source')
    return { count: new Set(features.map(feature => feature.properties?.selection_key)).size, type: features[0]?.properties?.feature_type }
  })).toEqual({ count: 1, type: featureType })
}

test('the host selection overlay handles generic and OSM polygons', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockMapData(page)
  await page.goto('/karte')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })

  await clickCoordinate(page, [9.4305, 54.78035])
  await expectSelection(page, 'STADTPLANNER')
  await expect(page.getByText('Browser-Testfläche', { exact: true })).toBeVisible()

  await clickCoordinate(page, [9.43825, 54.784])
  await expectSelection(page, 'OSM_POLYGON')
  await expect(page.getByText('OSM-Testfläche', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'OSM-Auswahl schließen' }).click()
  await expect.poll(() => page.evaluate(() => window.__stadtplanerMapPerformance!.map.querySourceFeatures('selected-polygon-source').length)).toBe(0)
})
