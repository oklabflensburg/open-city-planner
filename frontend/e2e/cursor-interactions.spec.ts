import { expect, test } from '@playwright/test'

test.describe.configure({ mode: 'serial', timeout: 60_000 })

const providers = [
  { id: 'github', label: 'GitHub', requires_instance: false, default_instance: null },
  { id: 'google', label: 'Google', requires_instance: false, default_instance: null },
  { id: 'mastodon', label: 'Mastodon', requires_instance: true, default_instance: 'https://norden.social' }
]

for (const width of [1024, 1440, 1920]) {
  test(`shared interaction cursors are correct at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
    await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: providers }))
    await page.goto('/login')

    const loginButton = page.getByRole('button', { name: 'Anmelden', exact: true })
    await expect(loginButton).toBeVisible({ timeout: 20_000 })
    await expect(loginButton).toHaveCSS('cursor', 'pointer')
    await expect(page.getByLabel('E-Mail')).toHaveCSS('cursor', 'text')
    await expect(page.getByRole('button', { name: 'Mit Google fortfahren' })).toHaveCSS('cursor', 'pointer')
    await expect(page.locator('.civic-card').first()).not.toHaveCSS('cursor', 'pointer')

    await page.getByRole('button', { name: 'Mit Mastodon fortfahren' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Mastodon-Instanz').fill('')
    const continueButton = dialog.getByRole('button', { name: 'Weiter' })
    await expect(continueButton).toBeDisabled()
    await expect(continueButton).toHaveCSS('cursor', 'not-allowed')
  })
}

test('cursor changes preserve the auth layout at mobile widths', async ({ page }) => {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: providers }))
  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible({ timeout: 20_000 })

  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: 760 })
    await expect(page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})
