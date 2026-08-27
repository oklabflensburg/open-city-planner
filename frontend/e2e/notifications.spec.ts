import { expect, test, type Page } from '@playwright/test'
import { loginAs } from './support/auth'

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

const items = Array.from({ length: 36 }, (_, index) => ({
  id: `11111111-1111-4111-8111-${String(index).padStart(12, '0')}`,
  actor_user_id: null,
  actor_type: 'SYSTEM',
  event_type: index ? 'AREA_STATISTICS_UPDATED' : 'ROLE_ASSIGNED',
  category: index ? 'DATA' : 'ACCOUNT',
  priority: index ? 'INFO' : 'ACTION_REQUIRED',
  title: index ? `Statistik aktualisiert ${index}` : 'Rolle geändert',
  message: index ? 'Für Ihr gefolgtes Gebiet sind neue Daten verfügbar.' : 'Ihre Berechtigungen wurden aktualisiert.',
  resource_type: index ? 'AREA' : null,
  resource_id: index ? 'area-1' : null,
  resource_slug: index ? 'innenstadt' : null,
  action_url: index ? '/gebiete/innenstadt' : '/profil',
  action_label: 'Öffnen',
  is_read: index > 2,
  read_at: index > 2 ? '2026-08-16T12:00:00Z' : null,
  created_at: new Date(Date.UTC(2026, 7, 17, 12, 0, 0) - index * 60_000).toISOString(),
  expires_at: null,
  metadata: {}
}))

async function mockNotifications(page: Page) {
  await loginAs(page)
  await page.addInitScript(() => {
    class MockEventSource {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSED = 2
      readonly CONNECTING = 0
      readonly OPEN = 1
      readonly CLOSED = 2
      readyState = 1
      url: string
      withCredentials = true
      onopen = null
      onmessage = null
      onerror = null
      constructor(url: string | URL) { this.url = String(url) }
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() { return true }
      close() { this.readyState = 2 }
    }
    Object.defineProperty(window, 'EventSource', { value: MockEventSource, configurable: true })
  })
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/subscriptions', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/preferences', route => route.fulfill({ json: {
    user_id: user.id,
    in_app_enabled: true,
    notify_gis: true,
    notify_osm: true,
    notify_area_updates: true,
    notify_social: true,
    notify_account: true,
    notify_system: true,
    updated_at: '2026-08-17T12:00:00Z'
  } }))
  await page.route('**/api/v1/notifications/unread-count', route => route.fulfill({ json: { unread_count: 3 } }))
  await page.route('**/api/v1/notifications/read-all', route => route.fulfill({ status: 204 }))
  await page.route('**/api/v1/notifications/*/read', route => route.fulfill({ status: 204 }))
  await page.route('**/api/v1/notifications?*', (route) => {
    const pageNumber = Number(new URL(route.request().url()).searchParams.get('page') || '1')
    const pageItems = pageNumber === 1 ? items.slice(0, 30) : items.slice(30)
    return route.fulfill({ json: { items: pageItems, total: items.length, unread_count: 3, page: pageNumber, page_size: 30, pages: 2 } })
  })
}

test('desktop bell, badge, read state and navigation work', async ({ page }) => {
  await mockNotifications(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/profil')

  const bell = page.locator('header').getByRole('button', { name: 'Benachrichtigungen' })
  await expect(bell).toContainText('3 ungelesene Benachrichtigungen')
  await bell.click()
  const center = page.locator('[role="dialog"][aria-label="Benachrichtigungen"]')
  await expect(center).toBeVisible()
  await center.getByRole('button', { name: /Rolle geändert/ }).click()
  await expect(page).toHaveURL(/\/profil$/)
  await expect(center).toBeHidden()
})

test('mobile notification center uses one scrollable bottom sheet without horizontal overflow', async ({ page }) => {
  await mockNotifications(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/profil')
  await page.locator('header').getByRole('button', { name: 'Benachrichtigungen' }).click()

  const sheet = page.getByRole('dialog', { name: 'Benachrichtigungen' })
  await expect(sheet).toBeVisible()
  await expect(sheet.getByText('Statistik aktualisiert 1', { exact: true })).toBeVisible()
  await sheet.getByRole('button', { name: 'Mehr laden' }).click()
  await expect(sheet.getByText('Statistik aktualisiert 35', { exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
