import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 60_000 })

const user = {
  id: '22222222-2222-4222-8222-222222222222',
  email: 'ada@example.org',
  first_name: 'Ada',
  last_name: 'Planerin',
  display_name: 'Ada Planerin mit langem Namen',
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

async function mockOverview(page: Page, session = { authenticated: true }) {
  await page.route('**/api/v1/auth/session', route => session.authenticated
    ? route.fulfill({ json: { user, csrf_token: 'header-csrf' } })
    : route.fulfill({ status: 401, json: { detail: { error: { code: 'AUTH_REQUIRED', message: 'Bitte anmelden.' } } } }))
  await page.route('**/api/v1/auth/logout', async (route) => {
    session.authenticated = false
    await route.fulfill({ json: { message: 'Abgemeldet.' } })
  })
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/subscriptions', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications?*', route => route.fulfill({ json: { items: [], total: 0, unread_count: 0, page: 1, page_size: 30, pages: 1 } }))
  await page.route('**/api/v1/polygons/overview**', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/analytics/overview**', route => route.fulfill({ json: {
    fast_facts: { shops: 0, polygon_count: 0, total_area_m2: null, average_area_m2: null, median_area_m2: null, vacant_area_m2: null, vacancy_area_rate: null, calculated_vacancy_rate: null, calculated_chain_store_rate: null, known_occupancy_count: 0, known_business_structure_count: 0, data_updated_at: null, vacancy_rate: null, chain_store_rate: null, centrality_index: null, purchasing_power_index: null, reference_date: null, source: null, updated_at: null },
    industry_distribution: [], category_counts: [], size_distribution: [], floor_distribution: [], status_distribution: [], business_structure_distribution: [], data_completeness: [],
    prime_rents: { unit: 'EUR_PER_SQM', period: null, rows: [] }
  } }))
  await page.route('**/api/v1/analysis-areas', route => route.fulfill({ json: [] }))
  await page.route(/\/api\/v1\/analysis-areas\/geojson(?:\?.*)?$/, route => route.fulfill({ json: { type: 'FeatureCollection', features: [] } }))
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection', features: [], meta: { count: 0, summary: {}, canonical_summary: {}, canonical_facets: {}, business_count: 0, context_count: 0, deduplicated_linked_count: 0, truncated: false, zoom: 17, osm_data_updated_at: null }
  } }))
}

function trackHydrationWarnings(page: Page) {
  const warnings: string[] = []
  page.on('console', (message) => {
    if (/hydration (?:node|children|attribute|class|style|text content|completed)/i.test(message.text())) warnings.push(message.text())
  })
  return warnings
}

test('desktop create CTA stays on one line without colliding with adjacent actions', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  const hydrationWarnings = trackHydrationWarnings(page)
  await mockOverview(page)
  await page.goto('/karte')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })

  const cta = page.locator('[data-header-create-cta]')
  const notifications = page.locator('[data-header-notifications]')
  const account = page.locator('[data-header-account]')

  for (const viewport of [
    { width: 1024, height: 768 }, { width: 1280, height: 800 }, { width: 1366, height: 768 },
    { width: 1440, height: 900 }, { width: 1920, height: 1080 }
  ]) {
    await page.setViewportSize(viewport)
    await expect(cta).toBeVisible()
    await expect(cta).toContainText('Neue Fläche')
    const metrics = await cta.evaluate(element => ({
      whiteSpace: getComputedStyle(element).whiteSpace,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
      scrollWidth: element.scrollWidth
    }))
    expect(metrics.whiteSpace).toBe('nowrap')
    expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight)
    expect(metrics.scrollWidth).toBeLessThanOrEqual(220)

    const [notificationBox, ctaBox, accountBox] = await Promise.all([
      notifications.boundingBox(), cta.boundingBox(), account.boundingBox()
    ])
    expect(notificationBox!.x + notificationBox!.width).toBeLessThanOrEqual(ctaBox!.x)
    expect(ctaBox!.x + ctaBox!.width).toBeLessThanOrEqual(accountBox!.x)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  }

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('banner').screenshot({ path: 'test-results/header-create-cta-1440.png' })
  expect(hydrationWarnings).toEqual([])
})

test('mobile exposes authenticated creation as a floating action without covering the tool bar', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })
  const hydrationWarnings = trackHydrationWarnings(page)
  const session = { authenticated: true }
  await mockOverview(page, session)
  await page.goto('/karte')

  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: 844 })
    await expect(page.getByRole('button', { name: 'Navigation öffnen' })).toBeVisible()
    await expect(page.locator('[data-header-create-cta]')).toBeHidden()
    const actionBar = page.locator('[data-mobile-map-actions]')
    const createFab = page.locator('[data-mobile-create-fab]')
    await expect(actionBar.getByRole('button')).toHaveCount(3)
    await expect(createFab).toBeVisible()
    await expect(createFab).toHaveAttribute('href', '/flaechen/neu')
    await expect(createFab).toHaveAttribute('aria-label', 'Neue Fläche anlegen')
    const [actionBarBox, createFabBox] = await Promise.all([
      actionBar.boundingBox(), createFab.boundingBox()
    ])
    expect(createFabBox!.width).toBeGreaterThanOrEqual(44)
    expect(createFabBox!.height).toBeGreaterThanOrEqual(44)
    expect(createFabBox!.x + createFabBox!.width).toBeLessThanOrEqual(width)
    expect(createFabBox!.y + createFabBox!.height).toBeLessThan(actionBarBox!.y)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  }

  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/mobile-create-fab-390.png' })
  await page.getByRole('button', { name: 'Suche öffnen' }).click()
  await expect(page.locator('[data-mobile-create-fab]')).toHaveCount(0)
  await page.goBack()
  await expect(page.locator('[data-mobile-create-fab]')).toBeVisible()
  session.authenticated = false
  await page.reload()
  await expect(page.locator('[data-mobile-create-fab]')).toHaveCount(0)
  expect(hydrationWarnings).toEqual([])
})

test('homepage navigation and signup CTA adapt to viewport and session', async ({ page }) => {
  const session = { authenticated: false }
  const hydrationWarnings = trackHydrationWarnings(page)
  await mockOverview(page, session)
  await page.goto('/')
  await page.waitForFunction(() => Boolean((document.querySelector('#__nuxt') as HTMLElement & { __vue_app__?: unknown })?.__vue_app__))
  await expect(page.getByRole('banner').getByRole('link', { name: 'Anmelden' })).toBeVisible()

  const logo = page.getByRole('banner').getByRole('link').first()
  await expect(logo).toHaveAttribute('href', '/')
  const desktopNavigation = page.getByRole('navigation', { name: 'Hauptnavigation' })
  await expect(desktopNavigation.getByRole('link', { name: 'Start', exact: true })).toHaveCount(0)
  for (const label of ['Karte', 'Gebiete', 'Über das Projekt', 'Dokumentation']) {
    await expect(desktopNavigation.getByRole('link', { name: label, exact: true })).toHaveCount(1)
  }

  const signup = page.locator('[data-home-signup-cta]')
  await expect(signup).toBeVisible()
  await expect(signup.getByRole('link', { name: 'Kostenlos registrieren' })).toHaveAttribute('href', '/registrieren')
  await expect(signup.getByRole('link', { name: 'Anmelden' })).toHaveAttribute('href', '/login')

  await page.setViewportSize({ width: 320, height: 844 })
  await page.getByRole('button', { name: 'Navigation öffnen' }).click()
  const mobileNavigation = page.getByRole('navigation', { name: 'Mobile Navigation' })
  await expect(mobileNavigation.getByRole('link', { name: 'Start', exact: true })).toHaveCount(0)
  await expect(mobileNavigation.getByRole('link', { name: 'Karte', exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)

  session.authenticated = true
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.reload()
  await expect(page.locator('[data-header-account]')).toBeVisible()
  await expect(page.locator('[data-home-signup-cta]')).toHaveCount(0)
  expect(hydrationWarnings).toEqual([])
})

test('account menu stays open until logout and ends the session', async ({ page }) => {
  const session = { authenticated: true }
  await mockOverview(page, session)
  await page.goto('/karte')
  await expect(page.getByRole('heading', { name: 'Interaktive Stadtkarte für Flensburg' })).toBeVisible()

  const accountButton = page.locator('[data-header-account]')
  await accountButton.click()
  const accountMenu = page.getByRole('menu')
  await expect(accountMenu).toBeVisible()
  await expect(accountButton).toHaveAttribute('aria-expanded', 'true')

  const logout = accountMenu.locator('[data-account-logout]')
  await expect(logout).toBeVisible()
  await expect(logout).toBeEnabled()
  await logout.click()

  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('link', { name: 'Anmelden' })).toBeVisible()
  expect(session.authenticated).toBe(false)
})
