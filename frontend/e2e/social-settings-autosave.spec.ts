import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })

const adminUser = {
  id: '22222222-2222-4222-8222-222222222222',
  email: 'admin@example.org',
  first_name: 'Ada',
  last_name: 'Admin',
  display_name: 'Ada Admin',
  avatar_url: null,
  is_active: true,
  is_verified: true,
  email_pending: false,
  is_superuser: true,
  roles: [],
  created_at: '2026-08-16T10:00:00Z',
  updated_at: '2026-08-16T10:00:00Z',
  last_login_at: null
}

const registry = [
  { event_type: 'AREA_CREATED', topic: 'AREAS', topic_label: 'Gebiete', label: 'Neue Gebiete', description: 'Neue öffentliche Gebiete.', default_enabled: true },
  { event_type: 'AREA_PUBLIC_DATA_UPDATED', topic: 'AREAS', topic_label: 'Gebiete', label: 'Gebietsdaten', description: 'Öffentliche Gebietsdaten.', default_enabled: true },
  { event_type: 'AREA_STATISTICS_UPDATED', topic: 'STATISTICS', topic_label: 'Statistik', label: 'Gebietskennzahlen', description: 'Öffentliche Kennzahlen.', default_enabled: true }
]

function initialSettings() {
  return {
    enabled: true,
    approval_mode: 'AUTOMATIC',
    default_visibility: 'public',
    language: 'de',
    debounce_seconds: 300,
    default_hashtags: ['Flensburg', 'OpenData', 'Stadtplaner'],
    enabled_events: ['AREA_CREATED', 'AREA_PUBLIC_DATA_UPDATED'],
    screenshot_viewport: 'LANDSCAPE_16_9',
    screenshot_show_map: true,
    screenshot_show_facts: true,
    screenshot_show_pois: false,
    screenshot_show_branding: true,
    screenshots_required: true,
    registry,
    updated_at: '2026-08-16T10:00:00Z'
  }
}

async function mockSocialSettings(page: Page) {
  const controller = {
    state: initialSettings(),
    patches: [] as Array<Record<string, unknown>>,
    patchAttempts: 0,
    refreshRequests: 0,
    activeRequests: 0,
    maxActiveRequests: 0,
    failNext: false,
    unauthorizedNext: false,
    holdNext: false,
    releasePatch: undefined as (() => void) | undefined
  }

  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: { user: adminUser, csrf_token: 'playwright-csrf' } }))
  await page.route('**/api/v1/auth/refresh', route => {
    controller.refreshRequests += 1
    return route.fulfill({ json: { user: adminUser, csrf_token: 'refreshed-csrf' } })
  })
  await page.route('**/api/v1/admin/social/mastodon/status', route => route.fulfill({
    json: {
      enabled: controller.state.enabled,
      configured: true,
      reachable: true,
      account: '@oklabflensburg@norden.social',
      account_url: 'https://norden.social/@oklabflensburg',
      area_updates_enabled: controller.state.enabled,
      dry_run: controller.state.approval_mode === 'DRY_RUN',
      visibility: controller.state.default_visibility,
      pending: 0,
      failed: 0,
      published: 0,
      last_publication_at: null,
      verification_error: null,
      approval_mode: controller.state.approval_mode,
      screenshots_required: true
    }
  }))
  await page.route('**/api/v1/admin/social/publications?*', route => route.fulfill({
    json: { items: [], total: 0, page: 1, page_size: 25, pages: 1 }
  }))
  await page.route('**/api/v1/admin/social/settings', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: controller.state })
      return
    }

    controller.patchAttempts += 1
    const patch = route.request().postDataJSON() as Record<string, unknown>
    controller.patches.push(patch)

    if (controller.unauthorizedNext) {
      controller.unauthorizedNext = false
      await route.fulfill({
        status: 401,
        json: { detail: { error: { code: 'ACCESS_TOKEN_EXPIRED', message: 'Sitzung abgelaufen.' } } }
      })
      return
    }

    controller.activeRequests += 1
    controller.maxActiveRequests = Math.max(controller.maxActiveRequests, controller.activeRequests)
    if (controller.holdNext) {
      controller.holdNext = false
      await new Promise<void>(resolve => { controller.releasePatch = resolve })
      controller.releasePatch = undefined
    }
    if (controller.failNext) {
      controller.failNext = false
      controller.activeRequests -= 1
      await route.fulfill({ status: 500, json: { detail: 'Speicherfehler' } })
      return
    }

    Object.assign(controller.state, patch, { updated_at: new Date().toISOString() })
    controller.activeRequests -= 1
    await route.fulfill({ json: controller.state })
  })

  return controller
}

test('master switch saves immediately without a global save button and survives reload', async ({ page }) => {
  const controller = await mockSocialSettings(page)
  await page.goto('/admin/social')

  const publishing = page.getByRole('switch', { name: 'Automatische Veröffentlichungen' })
  await expect(publishing).toBeChecked()
  await expect(page.getByRole('button', { name: 'Einstellungen speichern' })).toHaveCount(0)
  expect(controller.patchAttempts).toBe(0)

  controller.holdNext = true
  await publishing.click()
  await expect(publishing).not.toBeChecked()
  await expect(page.getByText('Speichern …', { exact: true })).toBeVisible()
  await expect.poll(() => controller.patchAttempts).toBe(1)
  expect(controller.patches[0]).toEqual({ enabled: false })
  controller.releasePatch?.()
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()

  await page.reload()
  await expect(page.getByRole('switch', { name: 'Automatische Veröffentlichungen' })).not.toBeChecked()
  expect(controller.patchAttempts).toBe(1)
})

test('hashtags save once after 600ms and preserve focus, scroll and mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const controller = await mockSocialSettings(page)
  await page.goto('/admin/social')

  const hashtags = page.getByLabel('Standard-Hashtags')
  await hashtags.scrollIntoViewIfNeeded()
  await hashtags.focus()
  const scrollBefore = await page.evaluate(() => window.scrollY)
  await hashtags.fill('')
  await hashtags.pressSequentially('Flensburg, OpenData, Autosave_Test', { delay: 15 })
  await expect(page.getByText('Speichern …', { exact: true })).toBeVisible()
  await page.waitForTimeout(300)
  expect(controller.patchAttempts).toBe(0)

  await expect.poll(() => controller.patchAttempts).toBe(1)
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()
  expect(controller.patches).toEqual([{ default_hashtags: ['Flensburg', 'OpenData', 'Autosave_Test'] }])
  await expect(hashtags).toBeFocused()
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollBefore)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)

  await page.reload()
  await expect(page.getByLabel('Standard-Hashtags')).toHaveValue('Flensburg, OpenData, Autosave_Test')
})

test('changes made during a slow save are serialized and newest values win', async ({ page }) => {
  const controller = await mockSocialSettings(page)
  await page.goto('/admin/social')

  controller.holdNext = true
  await page.getByLabel('Sichtbarkeit').selectOption('unlisted')
  await expect.poll(() => controller.patchAttempts).toBe(1)

  await page.getByLabel('Vor Veröffentlichung freigeben').check()
  await page.getByLabel('POIs').check()
  controller.releasePatch?.()

  await expect.poll(() => controller.state.approval_mode).toBe('MANUAL')
  await expect.poll(() => controller.state.screenshot_show_pois).toBe(true)
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()
  expect(controller.state.default_visibility).toBe('unlisted')
  expect(controller.maxActiveRequests).toBe(1)
  expect(controller.patchAttempts).toBe(2)
  expect(controller.patches[1]).toEqual({ approval_mode: 'MANUAL', screenshot_show_pois: true })
})

test('failed settings remain pending and can be retried', async ({ page }) => {
  const controller = await mockSocialSettings(page)
  await page.goto('/admin/social')

  controller.failNext = true
  await page.getByLabel('Sichtbarkeit').selectOption('private')
  await expect(page.getByText('Speicherfehler', { exact: true })).toBeVisible()
  expect(controller.state.default_visibility).toBe('public')
  await expect(page.getByLabel('Sichtbarkeit')).toHaveValue('private')

  await page.getByRole('button', { name: 'Erneut versuchen' }).click()
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()
  expect(controller.state.default_visibility).toBe('private')
  expect(controller.patchAttempts).toBe(2)
})

test('expired access token is refreshed and the autosave request is retried', async ({ page }) => {
  const controller = await mockSocialSettings(page)
  await page.goto('/admin/social')

  controller.unauthorizedNext = true
  await page.getByRole('switch', { name: 'Automatische Veröffentlichungen' }).click()

  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()
  expect(controller.refreshRequests).toBe(1)
  expect(controller.patchAttempts).toBe(2)
  expect(controller.state.enabled).toBe(false)
})
