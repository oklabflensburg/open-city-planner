import { expect, test } from '@playwright/test'

const publicationId = '11111111-1111-4111-8111-111111111111'
const approvalPublicationId = '44444444-4444-4444-8444-444444444444'

test('public social preview exposes an explicit ready state without authentication', async ({ page }) => {
  await page.goto('/gebiete/flensburg-27020?social-preview=1&map=0')
  const preview = page.locator('[data-social-preview-capture]')
  await expect(preview).toBeVisible()
  await expect(preview).toHaveAttribute('data-social-preview-ready', 'true')
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,nofollow')
})

test('polygon detail social preview is public and excludes editing controls', async ({ page, request }) => {
  const response = await request.get('http://127.0.0.1:8010/api/v1/polygons')
  expect(response.ok()).toBe(true)
  const polygons = await response.json() as Array<{ id: string, slug: string, name: string }>
  expect(polygons.length).toBeGreaterThan(0)

  await page.goto(`/flaechen/${polygons[0]!.slug}?social-preview=1&map=0`)
  const preview = page.locator('[data-social-preview-capture]')
  await expect(preview).toBeVisible()
  await expect(preview).toHaveAttribute('data-social-preview-ready', 'true')
  await expect(preview.getByRole('heading', { name: polygons[0]!.name })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Polygon bearbeiten' })).toHaveCount(0)
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,nofollow')
})

test('GIS social deep link selects the polygon before declaring the map ready', async ({ page, request }) => {
  const response = await request.get('http://127.0.0.1:8010/api/v1/polygons/overview')
  const polygons = await response.json() as Array<{ id: string, slug: string, name: string, bbox?: number[] }>
  expect(polygons.length).toBeGreaterThan(0)
  const selected = polygons[0]!
  const metricsResponse = await request.get(`http://127.0.0.1:8010/api/v1/polygons/${selected.id}/metrics`)
  const osmResponse = await request.get(`http://127.0.0.1:8010/api/v1/polygons/by-slug/${selected.slug}/osm`)
  const metrics = await metricsResponse.json()
  const osm = await osmResponse.json()
  await page.route('**/api/v1/polygons/overview*', route => route.fulfill({ json: [selected] }))
  await page.route(`**/api/v1/polygons/${selected.id}/metrics`, route => route.fulfill({ json: metrics }))
  await page.route(`**/api/v1/polygons/by-slug/${selected.slug}/osm`, route => route.fulfill({ json: osm }))

  await page.goto(`/?polygon=${selected.id}&social-preview=1`)
  await expect(page.locator('[data-social-preview-capture]')).toBeVisible()
  await expect(page.locator('[data-social-preview-ready="true"]')).toBeVisible({ timeout: 30_000 })
  await expect(page).toHaveURL(new RegExp(`polygon=${selected.id}`))
})

test('superuser can inspect social publishing and queue a failed event for retry', async ({ page }) => {
  let retryRequested = false
  let approvalRequested = false

  await page.route('**/api/v1/auth/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      user: {
        id: '22222222-2222-4222-8222-222222222222',
        email: 'admin@example.org',
        first_name: 'Ada',
        last_name: 'Admin',
        display_name: 'Ada Admin',
        is_active: true,
        is_verified: true,
        is_superuser: true,
        roles: [],
        created_at: '2026-08-16T10:00:00Z',
        updated_at: '2026-08-16T10:00:00Z'
      },
      csrf_token: 'playwright-csrf'
    })
  }))
  await page.route('**/api/v1/admin/social/mastodon/status', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      enabled: true,
      configured: true,
      reachable: true,
      account: '@oklabflensburg@norden.social',
      account_url: 'https://norden.social/@oklabflensburg',
      area_updates_enabled: true,
      dry_run: false,
      visibility: 'public',
      pending: 1,
      failed: 1,
      published: 7,
      last_publication_at: '2026-08-16T10:00:00Z',
      verification_error: null,
      approval_mode: 'MANUAL',
      screenshots_required: true
    })
  }))
  await page.route('**/api/v1/admin/social/settings', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      enabled: true, approval_mode: 'MANUAL', default_visibility: 'public', language: 'de',
      debounce_seconds: 300, default_hashtags: ['Flensburg', 'OpenData', 'Stadtplaner'],
      enabled_events: ['AREA_CREATED', 'AREA_PUBLIC_DATA_UPDATED', 'AREA_BOUNDARY_UPDATED'],
      screenshot_viewport: 'LANDSCAPE_16_9', screenshot_show_map: true,
      screenshot_show_facts: true, screenshot_show_pois: false, screenshot_show_branding: true,
      polygon_osm_adoption_link_target: 'DETAIL_PAGE',
      screenshots_required: true, updated_at: '2026-08-16T10:00:00Z',
      registry: [
        { event_type: 'AREA_CREATED', topic: 'AREAS', topic_label: 'Gebiete', label: 'Neue Gebiete', description: 'Neue öffentliche Gebiete.', default_enabled: true },
        { event_type: 'AREA_PUBLIC_DATA_UPDATED', topic: 'AREAS', topic_label: 'Gebiete', label: 'Gebietsdaten', description: 'Öffentliche Gebietsdaten.', default_enabled: true },
        { event_type: 'AREA_BOUNDARY_UPDATED', topic: 'AREAS', topic_label: 'Gebiete', label: 'Gebietsgrenzen', description: 'Wesentliche Grenzänderungen.', default_enabled: true }
      ]
    })
  }))
  await page.route('**/api/v1/admin/social/publications?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      items: [{
        id: publicationId,
        created_at: '2026-08-16T10:00:00Z',
        event_type: 'AREA_PUBLIC_DATA_UPDATED',
        resource_type: 'ANALYSIS_AREA',
        resource_id: '33333333-3333-4333-8333-333333333333',
        resource_name: 'Flensburg Innenstadt',
        resource_slug: 'flensburg-innenstadt',
        status: retryRequested ? 'PENDING' : 'FAILED',
        attempt_count: retryRequested ? 0 : 5,
        next_attempt_at: '2026-08-16T10:00:00Z',
        published_at: null,
        last_error: retryRequested ? null : 'HTTP 503: Mastodon vorübergehend nicht erreichbar',
        remote_url: null,
        changed_fields: ['name'],
        dry_run: false,
        screenshot_ready: false,
        screenshot_target_url: null,
        screenshot_alt_text: null
      }, {
        id: approvalPublicationId,
        created_at: '2026-08-16T11:00:00Z',
        event_type: 'AREA_CREATED',
        resource_type: 'ANALYSIS_AREA',
        resource_id: '55555555-5555-4555-8555-555555555555',
        resource_name: 'Neues Gebiet',
        resource_slug: 'neues-gebiet',
        status: approvalRequested ? 'PENDING' : 'PENDING_APPROVAL',
        attempt_count: 0,
        next_attempt_at: '2026-08-16T11:00:00Z',
        published_at: null,
        last_error: null,
        remote_url: null,
        changed_fields: [],
        dry_run: false,
        screenshot_ready: false,
        screenshot_status: 'PENDING',
        screenshot_target_url: null,
        screenshot_alt_text: null,
        allowed_actions: approvalRequested
          ? ['PREVIEW', 'DISCARD', 'OPEN_RESOURCE']
          : ['PREVIEW', 'APPROVE_AND_PUBLISH', 'DISCARD', 'OPEN_RESOURCE'],
        blocking_reasons: []
      }],
      total: 2,
      page: 1,
      page_size: 25,
      pages: 1
    })
  }))
  await page.route(`**/api/v1/admin/social/publications/${publicationId}/retry`, async (route) => {
    retryRequested = true
    expect(route.request().method()).toBe('POST')
    expect(route.request().headers()['x-csrf-token']).toBe('playwright-csrf')
    await route.fulfill({ status: 204 })
  })
  await page.route(`**/api/v1/admin/social/publications/${approvalPublicationId}/approve-and-publish`, async (route) => {
    approvalRequested = true
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({})
    expect(route.request().headers()['x-csrf-token']).toBe('playwright-csrf')
    await route.fulfill({ status: 204 })
  })

  await page.goto('/admin/social')

  await expect(page.getByRole('heading', { name: 'Social Publishing' })).toBeVisible()
  await expect(page.getByText('Verbunden', { exact: true })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole('link', { name: '@oklabflensburg@norden.social', exact: true })).toHaveAttribute('href', 'https://norden.social/@oklabflensburg')
  await expect(page.getByRole('heading', { name: 'Publication History' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Automatische Veröffentlichungen' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Screenshot-Einstellungen' })).toBeVisible()
  await expect(page.getByText('Flensburg Innenstadt')).toBeVisible()
  await expect(page.getByText('Neues Gebiet')).toBeVisible()
  const approvalCard = page.getByText('Neues Gebiet').locator('xpath=ancestor::*[self::article or self::div][.//button[contains(., "Freigeben")]][1]')
  await expect(page.getByRole('button', { name: 'Freigeben & veröffentlichen' })).toBeEnabled()
  await expect(page.getByText('Der Pflicht-Screenshot wird nach der Freigabe automatisch erstellt.')).toBeVisible()
  await approvalCard.getByRole('button', { name: 'Freigeben & veröffentlichen' }).click()
  await expect.poll(() => approvalRequested).toBe(true)
  await expect(page.getByText('Screenshot wird automatisch erstellt …')).toBeVisible()

  await page.getByRole('button', { name: 'Erneut versuchen' }).click()
  await expect(page.getByRole('heading', { name: 'Veröffentlichung erneut versuchen?' })).toBeVisible()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Erneut versuchen' }).click()

  await expect.poll(() => retryRequested).toBe(true)
  await expect(page.locator('span').filter({ hasText: /^Wird vorbereitet$/ })).toHaveCount(2)
})
