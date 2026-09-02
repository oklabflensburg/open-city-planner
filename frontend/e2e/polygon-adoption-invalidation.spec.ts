import { expect, test } from '@playwright/test'
import { loginAs } from './support/auth'

const polygonId = '55555555-5555-4555-8555-555555555555'
const geometry = { type: 'Polygon' as const, coordinates: [[[9.4348, 54.7828], [9.4352, 54.7828], [9.4352, 54.7832], [9.4348, 54.7828]]] }
const polygon = {
  id: polygonId, slug: 'osm-mode-adoptiert', name: 'OSM Mode', description: null, floor: 'EG', area_size: 'S', address_display_name: 'Holm 1, Flensburg',
  address_street: 'Holm', address_house_number: '1', address_postal_code: '24937', address_city: 'Flensburg', address_country: 'Deutschland', address_lookup_status: 'resolved',
  category: 'fashion', occupancy_status: 'UNKNOWN', occupancy_source: 'UNKNOWN', business_structure: 'UNKNOWN', geometry,
  external_links: { wikipedia: null },
  osm_sources: [{ osm_type: 'node', osm_id: 123, is_primary: true, imported_at: '2026-08-17T08:00:00Z' }],
  area_m2: 120, perimeter_m: 48, centroid: [9.435, 54.783], bbox: [9.4348, 54.7828, 9.4352, 54.7832],
  properties: {}, created_at: '2026-08-17T08:00:00Z', updated_at: '2026-08-17T08:00:00Z'
}
const osmFeature = {
  type: 'Feature', id: 'node/123', geometry: { type: 'Point', coordinates: [9.435, 54.783] },
  properties: {
    feature_id: 'node/123', osm_type: 'node', osm_id: 123, category: 'retail', canonical_category: 'fashion', name: 'OSM Mode', primary_type: 'clothes', natural: null,
    feature_type: 'point', source: 'OSM', canonical_floor: 'EG', mapped_area_m2: null, occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: []
  }
}

test('OSM adoption invalidates the same viewport and shows the persisted polygon after route return', async ({ page }) => {
  test.setTimeout(180_000)
  let adopted = false
  let countReturnRequests = false
  let adoptionRequests = 0
  let adoptedFloor: string | null | undefined
  let polygonRequestsAfterAdoption = 0
  let osmRequestsAfterAdoption = 0

  await loginAs(page)
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/unread-count', route => route.fulfill({ json: { unread_count: 0 } }))
  await page.route('**/api/v1/notifications/subscriptions', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications?*', route => route.fulfill({ json: { items: [], total: 0, page: 1, pages: 1, unread_count: 0 } }))
  await page.route('**/api/v1/osm/features/node/123', route => route.fulfill({ json: {
    osm_id: 123, osm_type: 'node', name: 'OSM Mode', category: 'retail', shop: 'clothes', level: '0', tags: { shop: 'clothes', level: '0' },
    centroid: { longitude: 9.435, latitude: 54.783 }, occupancy_status: 'UNKNOWN', occupancy_source: null,
    external_links: { wikipedia: null }
  } }))
  await page.route('**/api/v1/polygons/from-osm', async (route) => {
    adoptionRequests += 1
    adoptedFloor = route.request().postDataJSON().floor
    adopted = true
    await new Promise(resolve => setTimeout(resolve, 250))
    return route.fulfill({ status: 201, json: {
      id: polygonId, slug: polygon.slug, geometry_source: 'containing_osm_area', source_osm_type: 'node', source_osm_id: 123,
      occupancy_status: 'UNKNOWN', occupancy_source: 'UNKNOWN'
    } })
  })
  await page.route('**/api/v1/polygons/by-slug/osm-mode-adoptiert/osm', route => route.fulfill({ json: {
    polygon_id: polygonId, polygon_slug: polygon.slug, source: 'local', matches: [], primary_match: null
  } }))
  await page.route('**/api/v1/polygons/by-slug/osm-mode-adoptiert', route => route.fulfill({ json: polygon }))
  await page.route(`**/api/v1/polygons/${polygonId}/editor`, route => route.fulfill({ json: {
    ...polygon, can_edit_public_fields: true, can_delete: true
  } }))
  await page.route('**/api/v1/polygons/overview**', route => {
    if (countReturnRequests) polygonRequestsAfterAdoption += 1
    return route.fulfill({ json: adopted ? [polygon] : [] })
  })
  await page.route('**/api/v1/osm/features?**', route => {
    if (countReturnRequests) osmRequestsAfterAdoption += 1
    return route.fulfill({ json: {
      type: 'FeatureCollection', features: adopted ? [] : [osmFeature],
      meta: { count: adopted ? 0 : 1, summary: {}, canonical_summary: adopted ? {} : { fashion: 1 }, canonical_facets: { fashion: 1 }, business_count: adopted ? 0 : 1,
        context_count: 0, deduplicated_linked_count: adopted ? 1 : 0, truncated: false, zoom: 17, osm_data_updated_at: '2026-08-17T08:00:00Z' }
    } })
  })

  let before!: { x: number, y: number, center: number[], zoom: number }
  const viewports = [{ width: 1024, height: 768 }, { width: 390, height: 844 }, { width: 1440, height: 900 }]
  for (const [index, viewport] of viewports.entries()) {
    await page.setViewportSize(viewport)
    await page.goto('/karte?categories=fashion&floors=EG')
    await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 30_000 })
    await expect.poll(() => page.evaluate(() => {
      const map = window.__stadtplanerMapPerformance?.map
      if (!map?.getLayer('osm-poi-circle')) return false
      const point = map.project([9.435, 54.783])
      return map.queryRenderedFeatures(point, { layers: ['osm-poi-circle'] }).some(feature => feature.properties.feature_id === 'node/123')
    })).toBe(true)
    before = await page.evaluate(() => {
      const map = window.__stadtplanerMapPerformance!.map
      const point = map.project([9.435, 54.783])
      const rect = map.getCanvas().getBoundingClientRect()
      return { x: rect.left + point.x, y: rect.top + point.y, center: [map.getCenter().lng, map.getCenter().lat], zoom: map.getZoom() }
    })
    await page.mouse.click(before.x, before.y)
    await page.getByRole('button', { name: 'Als Fläche übernehmen' }).click()
    const modal = page.getByRole('dialog', { name: 'OpenStreetMap-Objekt übernehmen?' })
    const content = modal.locator('[data-app-modal-content]')
    const footer = modal.locator('[data-app-modal-footer]')
    const cancelButton = footer.getByRole('button', { name: 'Abbrechen' })
    const importButton = footer.getByRole('button', { name: 'Fläche übernehmen' })

    await expect(modal).toBeVisible()
    await expect(cancelButton).toBeVisible()
    await expect(importButton).toBeVisible()
    expect(await content.evaluate((element, candidate) => element.contains(candidate), await footer.elementHandle())).toBe(false)
    const [modalBox, footerBox] = await Promise.all([modal.boundingBox(), footer.boundingBox()])
    expect(footerBox!.y).toBeGreaterThanOrEqual(modalBox!.y)
    expect(footerBox!.y + footerBox!.height).toBeLessThanOrEqual(modalBox!.y + modalBox!.height + 1)
    expect(footerBox!.y + footerBox!.height).toBeLessThanOrEqual(viewport.height)
    if (viewport.width >= 1440) {
      expect(await content.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true)
    }
    if (index < viewports.length - 1) {
      await cancelButton.click()
      await expect(modal).toBeHidden()
      continue
    }
    await modal.getByLabel('Etage').selectOption('1OG')
    await importButton.click()
    await expect(footer.getByRole('button', { name: 'Wird übernommen …' })).toBeDisabled()
    await expect(cancelButton).toBeDisabled()
    await expect(modal.getByRole('button', { name: 'OpenStreetMap-Objekt übernehmen? schließen' })).toBeDisabled()
  }

  await expect(page).toHaveURL(`/flaechen/${polygon.slug}`)
  await expect(page.getByRole('status').filter({ hasText: 'Fläche wurde in den Stadtplaner übernommen.' })).toBeVisible()
  expect(adoptionRequests).toBe(1)
  expect(adoptedFloor).toBe('1OG')
  countReturnRequests = true
  await page.goBack()

  await expect(page).toHaveURL(/categories=fashion.*floors=EG|floors=EG.*categories=fashion/)
  await expect.poll(() => page.evaluate((id) => {
    const map = window.__stadtplanerMapPerformance?.map
    return map?.querySourceFeatures('overview-polygons').some(feature => feature.id === id || feature.properties.id === id) || false
  }, polygonId)).toBe(true)
  const after = await page.evaluate(() => {
    const map = window.__stadtplanerMapPerformance!.map
    return { center: [map.getCenter().lng, map.getCenter().lat], zoom: map.getZoom() }
  })
  expect(after.center[0]).toBeCloseTo(before.center[0], 5)
  expect(after.center[1]).toBeCloseTo(before.center[1], 5)
  expect(after.zoom).toBeCloseTo(before.zoom, 3)
  expect(polygonRequestsAfterAdoption).toBe(1)
  expect(osmRequestsAfterAdoption).toBe(1)

  await page.reload()
  await expect.poll(() => page.evaluate((id) => {
    const map = window.__stadtplanerMapPerformance?.map
    return map?.querySourceFeatures('overview-polygons').some(feature => feature.id === id || feature.properties.id === id) || false
  }, polygonId)).toBe(true)
})
