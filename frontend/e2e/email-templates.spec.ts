import { expect, test, type Page } from '@playwright/test'
import { loginAs } from './support/auth'

async function session(page: Page, superuser: boolean) {
  await loginAs(page, superuser ? 'admin' : 'account')
  await page.route('**/api/v1/notifications?*', route => route.fulfill({
    json: { items: [], total: 0, page: 1, page_size: 30, pages: 1, unread_count: 0 }
  }))
  await page.route('**/api/v1/notifications/subscriptions', route => route.fulfill({ json: [] }))
}

test('superuser previews, saves and resets an email template', async ({ page }) => {
  await session(page, true)
  let subject = 'Passwort zurücksetzen – OK Lab Flensburg'
  let version = 0
  let customized = false
  const detail = () => ({
    key: 'password_reset',
    name: 'Passwort zurücksetzen',
    description: 'Sicherer Link zum Zurücksetzen eines Passworts.',
    category: 'Sicherheit',
    subject,
    html_body: '<p>Hallo {{ name }}</p><p><a href="{{ reset_url }}">Passwort zurücksetzen</a></p>',
    text_body: 'Hallo {{ name }}\n{{ reset_url }}',
    allowed_variables: ['name', 'reset_url', 'expires_minutes'],
    required_variables: ['reset_url'],
    customized,
    version,
    active: true,
    security_sensitive: true,
    updated_at: null,
    updated_by: null
  })
  await page.route('**/api/v1/admin/email-templates', route => route.fulfill({ json: [detail()] }))
  await page.route('**/api/v1/admin/email-templates/password_reset', async (route) => {
    if (route.request().method() === 'PATCH') {
      subject = (await route.request().postDataJSON()).subject
      version += 1
      customized = true
    }
    await route.fulfill({ json: detail() })
  })
  await page.route('**/api/v1/admin/email-templates/password_reset/preview', route => route.fulfill({
    json: {
      subject: 'Geänderter Betreff',
      html: '<!doctype html><html lang="de"><body><p>Vorschau</p></body></html>',
      text: 'Vorschau'
    }
  }))
  await page.route('**/api/v1/admin/email-templates/password_reset/reset', async (route) => {
    subject = 'Passwort zurücksetzen – OK Lab Flensburg'
    version += 1
    customized = false
    await route.fulfill({ json: detail() })
  })

  await page.goto('/admin/email-vorlagen')
  await page.getByRole('link', { name: 'Vorlage bearbeiten' }).click()
  await page.getByLabel('Betreff').fill('Geänderter Betreff')
  await page.getByRole('button', { name: 'Vorschau', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'E-Mail-Vorschau' })
  await expect(dialog).toContainText('Geänderter Betreff')
  await expect(dialog.locator('iframe')).toHaveAttribute('sandbox', '')
  await dialog.getByRole('button', { name: 'E-Mail-Vorschau schließen' }).click()
  await page.getByRole('button', { name: 'Änderungen speichern' }).click()
  await expect(page.getByRole('status')).toContainText('gespeichert')

  await page.reload()
  await expect(page.getByLabel('Betreff')).toHaveValue('Geänderter Betreff')
  await page.getByRole('button', { name: 'Standard wiederherstellen' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Standard wiederherstellen' }).click()
  await expect(page.getByLabel('Betreff')).toHaveValue('Passwort zurücksetzen – OK Lab Flensburg')
})

test('normal users cannot access email template administration', async ({ page }) => {
  await session(page, false)
  await page.goto('/admin/email-vorlagen')
  await expect(page).toHaveURL('/', { timeout: 15_000 })
  await expect(page.getByRole('heading', { name: 'E-Mail-Vorlagen' })).toHaveCount(0)
})
