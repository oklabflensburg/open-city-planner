import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })

const actorId = '22222222-2222-4222-8222-222222222222'
const resourceId = '41056c8c-7406-4ba4-86fd-8a4c5f97cff1'
const longEmail = 'extremely-long-email-address-for-responsive-testing@example-subdomain.oklabflensburg.de'
const longName = 'very-long-user-name-without-natural-breakpoints-123456789'
const longResource = 'Ein-sehr-langer-Gebiets-oder-Polygonname-ohne-natuerliche-Trennstellen-123456789'
const longSummary = 'Die Einstellungen für Social Publishing wurden durch einen Superuser aktualisiert und betreffen mehrere Mastodon-Themen, automatische Screenshots und Veröffentlichungseinstellungen für @oklabflensburg@norden.social.'

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
  { width: 768, height: 1024 },
  { width: 820, height: 1180 },
  { width: 1024, height: 768 },
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 }
]

async function mockAuditLog(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    json: {
      user: {
        id: actorId,
        email: longEmail,
        first_name: 'Ada',
        last_name: 'Admin',
        display_name: longName,
        avatar_url: null,
        is_active: true,
        is_verified: true,
        email_pending: false,
        is_superuser: true,
        roles: [],
        created_at: '2026-08-16T10:00:00Z',
        updated_at: '2026-08-16T10:00:00Z',
        last_login_at: null
      },
      csrf_token: 'playwright-csrf'
    }
  }))
  await page.route('**/api/v1/admin/users?*', route => route.fulfill({
    json: {
      items: [{
        id: actorId,
        email: longEmail,
        first_name: 'Ada',
        last_name: 'Admin',
        display_name: longName,
        avatar_url: null,
        is_active: true,
        is_verified: true,
        is_superuser: true,
        roles: [],
        created_at: '2026-08-16T10:00:00Z',
        last_login_at: null,
        oauth_providers: ['mastodon']
      }],
      total: 1,
      page: 1,
      page_size: 100
    }
  }))
  await page.route('**/api/v1/admin/audit-logs?*', route => route.fulfill({
    json: {
      items: [{
        id: '11111111-1111-4111-8111-111111111111',
        created_at: '2026-08-16T17:01:15Z',
        action: 'VERY_LONG_AUDIT_ACTION_NAME_WITHOUT_SPACES',
        actor: { id: actorId, display_name: longName, email: longEmail },
        resource: { type: 'ANALYSIS_AREA_WITH_A_VERY_LONG_TYPE', id: resourceId, label: longResource },
        summary: longSummary,
        details: {
          changes: {
            very_long_field_name_without_breakpoints_123456789: {
              before: `https://example.org/${'before'.repeat(30)}`,
              after: `@oklabflensburg@norden.social/${'after'.repeat(30)}`
            }
          },
          resource_id: resourceId,
          url: `https://example.org/${'segment'.repeat(40)}`
        }
      }],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
      available_actions: ['VERY_LONG_AUDIT_ACTION_NAME_WITHOUT_SPACES']
    }
  }))
}

async function expectNoPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true)
}

for (const viewport of viewports) {
  test(`audit log has no horizontal page overflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await mockAuditLog(page)
    await page.goto('/admin/audit-log')
    await expect(page.getByRole('heading', { name: 'Auditlog' })).toBeVisible()

    if (viewport.width < 1024) {
      const list = page.getByRole('list', { name: 'Audit-Ereignisse' })
      await expect(list).toBeVisible()
      await expect(list.getByText(longEmail)).toBeVisible()
    } else {
      const table = page.getByRole('table').first()
      await expect(table).toBeVisible()
      await expect(table.getByText(longEmail)).toBeVisible()
    }
    await expectNoPageOverflow(page)
  })
}

test('audit detail dialog remains viewport-safe with long metadata', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuditLog(page)
  await page.goto('/admin/audit-log')
  await page.getByLabel('Aktion').selectOption('VERY_LONG_AUDIT_ACTION_NAME_WITHOUT_SPACES')
  await page.getByLabel('Ausgeführt von').selectOption(actorId)
  await expectNoPageOverflow(page)
  await page.getByRole('button', { name: 'Details ansehen' }).click()

  const dialog = page.getByRole('dialog', { name: 'Audit-Ereignis' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText(resourceId).first()).toBeVisible()
  await expect(dialog.getByText('Vorher', { exact: true }).first()).toBeVisible()
  await expectNoPageOverflow(page)

  await dialog.getByText('Technische Details').click()
  await expect(dialog.locator('pre')).toBeVisible()
  await expectNoPageOverflow(page)
})

test('audit log reflows at a 200-percent zoom equivalent', async ({ page }) => {
  // A 1280x900 browser viewport has a 640x450 CSS layout viewport at 200% zoom.
  await page.setViewportSize({ width: 640, height: 450 })
  await mockAuditLog(page)
  await page.goto('/admin/audit-log')

  await expect(page.getByRole('list', { name: 'Audit-Ereignisse' })).toBeVisible()
  await expect(page.getByLabel('Auditlog durchsuchen')).toBeVisible()
  await expectNoPageOverflow(page)
})
