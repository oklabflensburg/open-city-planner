import { expect, test, type Page } from '@playwright/test'

const user = {
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
  created_at: '2026-08-19T10:00:00Z',
  updated_at: '2026-08-19T10:00:00Z',
  last_login_at: null
}

async function mockSession(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    json: { user, csrf_token: 'email-center-csrf' }
  }))
  await page.route('**/api/v1/notifications?*', route => route.fulfill({
    json: { items: [], total: 0, page: 1, page_size: 30, pages: 1, unread_count: 0 }
  }))
  await page.route('**/api/v1/notifications/subscriptions', route => route.fulfill({ json: [] }))
}

test('Superuser bereitet eine Newsletter-Rundmail kontrolliert vor', async ({ page }) => {
  await mockSession(page)
  const id = '33333333-3333-4333-8333-333333333333'
  let campaign = {
    id,
    internal_name: 'Projektneuigkeiten August',
    subject: 'Neuigkeiten aus dem Stadtplaner',
    title: 'Projektneuigkeiten',
    intro: 'Das ist neu.',
    content_html: '<p>Neue Funktionen stehen bereit.</p>',
    content_text: 'Neue Funktionen stehen bereit.',
    action_url: '/dokumentation',
    action_label: 'Mehr erfahren',
    campaign_type: 'NEWSLETTER',
    status: 'DRAFT',
    recipient_scope: 'VERIFIED_USERS',
    created_at: '2026-08-19T10:00:00Z',
    updated_at: '2026-08-19T10:00:00Z',
    scheduled_at: null,
    started_at: null,
    completed_at: null,
    recipient_count: 0,
    sent_count: 0,
    failed_count: 0,
    skipped_count: 0,
    version: 1
  }
  await page.route('**/api/v1/admin/email-campaigns**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/preview')) return route.fulfill({ json: { subject: campaign.subject, html: '<html><body>Vorschau</body></html>', text: 'Vorschau' } })
    if (path.endsWith('/test-send')) return route.fulfill({ json: { message: 'Die Test-E-Mail wurde an admin@example.org gesendet.' } })
    if (path.endsWith('/recipient-count')) return route.fulfill({ json: { recipient_count: 42 } })
    if (request.method() === 'POST' && path.endsWith('/email-campaigns')) {
      campaign = { ...campaign, ...(await request.postDataJSON()) }
    }
    return route.fulfill({ json: campaign })
  })

  await page.goto('/admin/email-zentrale/rundmails/neu')
  await page.getByLabel('Interner Name').fill(campaign.internal_name)
  await page.getByLabel('Betreff').fill(campaign.subject)
  await page.getByLabel('Titel').fill(campaign.title)
  await page.getByLabel('Einleitung').fill(campaign.intro)
  await page.getByLabel('HTML-Inhalt').fill(campaign.content_html)
  await page.getByLabel('Text-Version').fill(campaign.content_text)
  await page.getByRole('button', { name: 'Entwurf speichern' }).click()
  await expect(page).toHaveURL(`/admin/email-zentrale/rundmails/${id}`)

  await page.getByRole('button', { name: 'Vorschau' }).click()
  await expect(page.getByRole('dialog', { name: 'Rundmail-Vorschau' })).toContainText(campaign.subject)
  await page.getByRole('dialog').getByRole('button', { name: /schließen/i }).click()
  await page.getByRole('button', { name: 'Testmail an mich' }).click()
  await expect(page.getByRole('status')).toContainText('Test-E-Mail')
  await page.getByRole('button', { name: 'Versand vorbereiten' }).click()
  await expect(page.getByRole('dialog', { name: 'Rundmail versenden?' })).toContainText('42 Benutzer')
})

test('E-Mail- und Newsletter-Einstellungen bleiben nach Reload erhalten', async ({ page }) => {
  await mockSession(page)
  let preferences = {
    user_id: user.id,
    in_app_enabled: true,
    notify_gis: true,
    notify_osm: true,
    notify_area_updates: true,
    notify_social: true,
    notify_account: true,
    notify_system: true,
    email_enabled: false,
    email_notify_gis: false,
    email_notify_osm: false,
    email_notify_area_updates: false,
    email_notify_social: false,
    email_notify_system: false,
    newsletter_enabled: true,
    updated_at: '2026-08-19T10:00:00Z'
  }
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications/preferences', async (route) => {
    if (route.request().method() === 'PATCH') preferences = { ...preferences, ...(await route.request().postDataJSON()) }
    await route.fulfill({ json: preferences })
  })

  await page.goto('/profil#benachrichtigungen')
  await page.getByLabel('E-Mail-Benachrichtigungen aktivieren').check()
  await page.getByLabel('GIS per E-Mail').check()
  await page.getByRole('checkbox', { name: /Newsletter/ }).uncheck()
  await expect(page.getByRole('status')).toContainText('Gespeichert')
  await page.reload()
  await expect(page.getByLabel('E-Mail-Benachrichtigungen aktivieren')).toBeChecked()
  await expect(page.getByLabel('GIS per E-Mail')).toBeChecked()
  await expect(page.getByRole('checkbox', { name: /Newsletter/ })).not.toBeChecked()
})

test('öffentliche Newsletter-Abmeldung zeigt keine Kontodaten', async ({ page }) => {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    status: 401,
    json: { detail: 'Nicht angemeldet' }
  }))
  await page.route('**/api/v1/email/unsubscribe?*', route => route.fulfill({
    json: { success: true, message: 'Sie erhalten künftig keine freiwilligen Newsletter-E-Mails mehr.' }
  }))
  const unsubscribeResponse = page.waitForResponse('**/api/v1/email/unsubscribe?*')
  await page.goto(`/email-abmelden?token=${'a'.repeat(32)}`)
  await unsubscribeResponse
  await expect(page.getByRole('heading', { name: 'Abmeldung abgeschlossen' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('keine freiwilligen Newsletter-E-Mails')).toBeVisible()
  await expect(page.getByText(user.email)).toHaveCount(0)
})
