import { expect, test } from '@playwright/test'
import { loginAs } from './support/auth'

const id = '44444444-4444-4444-8444-444444444444'
const detail = {
  id, slug: 'delete-test', name: 'Delete Testfläche', description: null, floor: 'EG', area_size: 'M', address_display_name: 'Holm 1, Flensburg',
  address_lookup_status: 'resolved', category: 'fashion', occupancy_status: 'OCCUPIED', occupancy_source: 'MANUAL', business_structure: 'INDEPENDENT',
  geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]] },
  osm_sources: [{ osm_type: 'way', osm_id: 123, is_primary: true, imported_at: '2026-08-17T08:00:00Z' }],
  area_m2: 120, perimeter_m: 48, centroid: [9.4305, 54.7805], bbox: [9.43, 54.78, 9.431, 54.781],
  created_at: '2026-08-17T08:00:00Z', updated_at: '2026-08-17T08:00:00Z',
}

test('successful delete invalidates map and linked OSM suppression without reload', async ({ page }) => {
  test.setTimeout(60_000)
  let deleted = false
  await loginAs(page)
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/users/me/polygons', route => route.fulfill({ json: [{ ...detail, properties: { size: 'M' } }] }))
  await page.route('**/api/v1/polygons/by-slug/delete-test', route => deleted ? route.fulfill({ status: 404, json: { detail: 'Polygon not found' } }) : route.fulfill({ json: detail }))
  await page.route(`**/api/v1/polygons/${id}/editor`, route => route.fulfill({ json: { ...detail, can_edit_public_fields: true, can_delete: true } }))
  await page.route('**/api/v1/polygons/by-slug/delete-test/osm', route => route.fulfill({ json: { polygon_id: id, polygon_slug: 'delete-test', source: 'local', matches: [], primary_match: null } }))
  await page.route(`**/api/v1/polygons/${id}`, route => {
    if (route.request().method() !== 'DELETE') return route.continue()
    deleted = true
    return route.fulfill({ status: 204, body: '' })
  })
  await page.route('**/api/v1/polygons/overview**', route => route.fulfill({ json: deleted ? [] : [detail] }))
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection',
    features: deleted ? [{ type: 'Feature', id: 'way/123', geometry: detail.geometry, properties: { feature_id: 'way/123', osm_type: 'way', osm_id: 123, category: 'retail', canonical_category: 'fashion', name: 'OSM Ursprung', primary_type: 'clothes', natural: null, feature_type: 'polygon', source: 'OSM', canonical_floor: 'EG', mapped_area_m2: 120, occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: [] } }] : [],
    meta: { count: deleted ? 1 : 0, summary: {}, canonical_summary: deleted ? { fashion: 1 } : {}, canonical_facets: deleted ? { fashion: 1 } : {}, business_count: deleted ? 1 : 0, context_count: 0, deduplicated_linked_count: deleted ? 0 : 1, truncated: false, zoom: 17, osm_data_updated_at: '2026-08-17T08:00:00Z' },
  } }))

  await page.goto('/karte')
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => {
    window.history.pushState({}, '', '/flaechen/delete-test')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page).toHaveURL('/flaechen/delete-test')
  await page.getByRole('button', { name: 'Fläche löschen', exact: true }).click()
  await page.getByRole('alertdialog', { name: 'Fläche löschen?' }).getByRole('button', { name: 'Endgültig löschen' }).click()

  await expect(page).toHaveURL('/karte')
  await expect(page.getByRole('status').filter({ hasText: 'Fläche wurde gelöscht.' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => {
    const map = window.__stadtplanerMapPerformance?.map
    return {
      polygons: map?.querySourceFeatures('overview-polygons').length ?? -1,
      osm: map?.querySourceFeatures('osm-polygons').some(feature => feature.properties.feature_id === 'way/123') ?? false
    }
  })).toEqual({ polygons: 0, osm: true })

  await page.reload()
  await page.goto('/flaechen/delete-test')
  await expect(page).toHaveURL('/flaechen/delete-test')
  await expect(page.getByRole('heading', { name: 'Seite nicht gefunden' })).toBeVisible()
})
