import { expect, test } from '@playwright/test'

const publicationId = '11111111-1111-4111-8111-111111111111'

test('public social preview exposes an explicit ready state without authentication', async ({ page }) => {
  await page.goto('/gebiete/flensburg-27020?social-preview=1&map=0')
  const preview = page.locator('[data-social-preview-capture]')
  await expect(preview).toBeVisible()
  await expect(preview).toHaveAttribute('data-social-preview-ready', 'true')
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,nofollow')
})

test('superuser can inspect social publishing and queue a failed event for retry', async ({ page }) => {
  let retryRequested = false

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
      approval_mode: 'AUTOMATIC',
      screenshots_required: true
    })
  }))
  await page.route('**/api/v1/admin/social/settings', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      enabled: true, approval_mode: 'AUTOMATIC', default_visibility: 'public', language: 'de',
      debounce_seconds: 300, default_hashtags: ['Flensburg', 'OpenData', 'Stadtplaner'],
      enabled_events: ['AREA_CREATED', 'AREA_PUBLIC_DATA_UPDATED', 'AREA_BOUNDARY_UPDATED'],
      screenshot_viewport: 'LANDSCAPE_16_9', screenshot_show_map: true,
      screenshot_show_facts: true, screenshot_show_pois: false, screenshot_show_branding: true,
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
      }],
      total: 1,
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

  await page.goto('/admin/social')

  await expect(page.getByRole('heading', { name: 'Social Publishing' })).toBeVisible()
  await expect(page.getByText('Verbunden', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '@oklabflensburg@norden.social', exact: true })).toHaveAttribute('href', 'https://norden.social/@oklabflensburg')
  await expect(page.getByRole('heading', { name: 'Publication History' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Automatische Veröffentlichungen' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Screenshot-Einstellungen' })).toBeVisible()
  await expect(page.getByText('Flensburg Innenstadt')).toBeVisible()

  await page.getByRole('button', { name: 'Erneut versuchen' }).click()
  await expect(page.getByRole('heading', { name: 'Veröffentlichung erneut versuchen?' })).toBeVisible()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Erneut versuchen' }).click()

  await expect.poll(() => retryRequested).toBe(true)
  await expect(page.locator('span').filter({ hasText: /^Ausstehend$/ })).toBeVisible()
})
