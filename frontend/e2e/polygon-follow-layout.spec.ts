import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 60_000 })

const polygonId = '44444444-4444-4444-8444-444444444444'
const slug = 'alte-kaffeeroesterei'
const user = {
  id: '22222222-2222-4222-8222-222222222222',
  email: 'ada@example.org',
  first_name: 'Ada',
  last_name: 'Planerin',
  display_name: 'Ada Planerin',
  avatar_url: null,
  is_active: true,
  is_verified: true,
  email_pending: false,
  is_superuser: false,
  roles: [],
  created_at: '2026-08-16T10:00:00Z',
  updated_at: '2026-08-16T10:00:00Z',
  last_login_at: null
}
const polygon = {
  id: polygonId,
  slug,
  name: 'Alte Kaffeerösterei',
  description: null,
  floor: 'EG',
  area_size: 'M',
  address_display_name: 'Rote Straße 16, 24937 Flensburg',
  address_lookup_status: 'resolved',
  category: 'food',
  occupancy_status: 'OCCUPIED',
  occupancy_source: 'MANUAL',
  business_structure: 'INDEPENDENT',
  geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]] },
  osm_sources: [],
  area_m2: 221,
  perimeter_m: 68,
  centroid: [9.4305, 54.7805],
  bbox: [9.43, 54.78, 9.431, 54.781],
  created_at: '2026-08-17T08:00:00Z',
  updated_at: '2026-08-17T08:00:00Z'
}

async function mockDetail(page: Page, authenticated: boolean, initiallyFollowing = false) {
  let following = initiallyFollowing
  await page.addInitScript(() => {
    class MockEventSource {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSED = 2
      readonly CONNECTING = 0
      readonly OPEN = 1
      readonly CLOSED = 2
      readyState = 1
      onopen = null
      onmessage = null
      onerror = null
      constructor(public url: string | URL) {}
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() { return true }
      close() { this.readyState = 2 }
    }
    Object.defineProperty(window, 'EventSource', { value: MockEventSource, configurable: true })
  })
  await page.route('**/api/v1/auth/session', route => authenticated
    ? route.fulfill({ json: { user, csrf_token: 'follow-csrf' } })
    : route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/subscriptions', async (route) => {
    if (route.request().method() === 'PUT') {
      following = true
      return route.fulfill({ json: { resource_type: 'POLYGON', resource_id: polygonId, event_types: [], created_at: '2026-08-18T08:00:00Z' } })
    }
    await new Promise(resolve => setTimeout(resolve, 600))
    return route.fulfill({ json: following ? [{ resource_type: 'POLYGON', resource_id: polygonId, event_types: [], created_at: '2026-08-18T08:00:00Z' }] : [] })
  })
  await page.route(`**/api/v1/notifications/subscriptions/POLYGON/${polygonId}`, (route) => {
    following = false
    return route.fulfill({ status: 204, body: '' })
  })
  await page.route('**/api/v1/notifications?*', route => route.fulfill({ json: { items: [], total: 0, unread_count: 0, page: 1, page_size: 30, pages: 1 } }))
  await page.route('**/api/v1/polygons/overview**', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection', features: [], meta: { count: 0, summary: {}, canonical_summary: {}, canonical_facets: {}, business_count: 0, context_count: 0, deduplicated_linked_count: 0, truncated: false, zoom: 17, osm_data_updated_at: null }
  } }))
  await page.route(`**/api/v1/polygons/by-slug/${slug}`, route => route.fulfill({ json: polygon }))
  await page.route(`**/api/v1/polygons/${polygonId}/editor`, route => route.fulfill({ json: { ...polygon, can_edit_public_fields: true, can_delete: false } }))
  await page.route(`**/api/v1/polygons/by-slug/${slug}/osm`, route => route.fulfill({ json: { polygon_id: polygonId, polygon_slug: slug, source: 'local', matches: [], primary_match: null } }))
}

async function openDetail(page: Page) {
  await page.goto('/karte')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
  await page.evaluate((path) => {
    window.history.pushState({}, '', path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, `/flaechen/${slug}`)
  await expect(page.locator('[data-polygon-title]')).toBeVisible()
}

test('authenticated mobile keeps category, editable title, address, follow and metrics in a stable order', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockDetail(page, true)
  await openDetail(page)

  const category = page.locator('[data-polygon-category]')
  const title = page.locator('[data-polygon-title]')
  const address = page.locator('[data-polygon-address]')
  const action = page.locator('[data-polygon-follow-action]')
  const metrics = page.locator('[data-polygon-metrics]')
  const boxes = await Promise.all([category, title, address, action, metrics].map(locator => locator.boundingBox()))
  expect(boxes.every(Boolean)).toBe(true)
  expect(boxes[0]!.y).toBeLessThan(boxes[1]!.y)
  expect(boxes[1]!.y).toBeLessThan(boxes[2]!.y)
  expect(boxes[2]!.y).toBeLessThan(boxes[3]!.y)
  expect(boxes[3]!.y).toBeLessThan(boxes[4]!.y)

  const follow = page.getByRole('button', { name: 'Dieser Fläche folgen' })
  await expect(follow).toBeEnabled()
  const before = await action.boundingBox()
  const titleBefore = await title.boundingBox()
  await follow.click()
  await expect(page.getByRole('button', { name: 'Sie folgen dieser Fläche' })).toBeVisible()
  const after = await action.boundingBox()
  const titleAfter = await title.boundingBox()
  expect(after).toEqual(before)
  expect(titleAfter).toEqual(titleBefore)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('follow action remains compact on desktop and all target widths stay overflow-safe', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockDetail(page, true, true)
  await openDetail(page)
  await expect(page.getByRole('button', { name: 'Sie folgen dieser Fläche' })).toBeEnabled()

  const main = page.locator('[data-polygon-detail-main]')
  const action = page.locator('[data-polygon-follow-action]')
  const desktopMain = await main.boundingBox()
  const desktopAction = await action.boundingBox()
  expect(desktopAction!.x).toBeGreaterThan(desktopMain!.x)
  expect(desktopAction!.width).toBeLessThan(300)

  for (const viewport of [
    { width: 320, height: 568 }, { width: 360, height: 800 }, { width: 390, height: 844 },
    { width: 412, height: 915 }, { width: 430, height: 932 }, { width: 768, height: 1024 },
    { width: 1024, height: 768 }, { width: 1280, height: 800 }, { width: 1440, height: 900 }
  ]) {
    await page.setViewportSize(viewport)
    await expect.poll(() => page.locator('header').filter({ has: action }).evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  }

  await page.setViewportSize({ width: 320, height: 568 })
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' })
  await expect(page.getByRole('button', { name: 'Sie folgen dieser Fläche' })).toBeVisible()
  await expect.poll(() => page.locator('[data-polygon-follow-action]').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
})

test('anonymous detail uses the same action zone without an empty gap', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  await mockDetail(page, false)
  await openDetail(page)

  const login = page.getByRole('link', { name: 'Zum Folgen anmelden' })
  await expect(login).toBeVisible()
  await expect(login).toHaveAttribute('href', /\/login\?redirect=.*flaechen/)
  await expect(page.locator('[data-polygon-follow-action]')).toHaveCount(1)
  await expect(page.getByRole('button', { name: /Fläche folgen/ })).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
