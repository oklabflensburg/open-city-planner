import { expect, test } from '@playwright/test'
import { loginAs } from './support/auth'

const providers = [
  { id: 'github', label: 'GitHub', requires_instance: false, default_instance: null },
  { id: 'google', label: 'Google', requires_instance: false, default_instance: null },
  { id: 'mastodon', label: 'Mastodon', requires_instance: true, default_instance: 'https://norden.social' }
]

for (const viewport of [
  { name: 'mobile-320', width: 320, height: 720 },
  { name: 'desktop', width: 1280, height: 900 }
]) {
  test(`Mastodon instance dialog is accessible on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }))
    await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: providers }))
    let postedInstance = ''
    await page.route('**/api/v1/auth/oauth/mastodon/start', async (route) => {
      postedInstance = route.request().postDataJSON().instance
      await route.fulfill({ json: { authorization_url: 'http://127.0.0.1:3010/login?mastodon_redirect=mocked' } })
    })

    await page.goto('/login')
    await page.getByRole('button', { name: 'Mit Mastodon fortfahren' }).click()
    const dialog = page.getByRole('dialog', { name: 'Mit Mastodon fortfahren' })
    await expect(dialog).toBeVisible()
    const instance = dialog.getByLabel('Mastodon-Instanz')
    await expect(instance).toBeFocused()
    await expect(dialog).toContainText('Ihre Zugangsdaten geben Sie ausschließlich auf Ihrer Mastodon-Instanz ein.')
    await instance.fill('@stadtfreund@social.example')
    await dialog.getByRole('button', { name: 'Weiter' }).click()

    await page.waitForURL(/mastodon_redirect=mocked/)
    expect(postedInstance).toBe('@stadtfreund@social.example')
  })
}

test('authenticated profile starts Mastodon linking without visiting login', async ({ page }) => {
  await loginAs(page)
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: providers }))
  await page.route('**/api/v1/users/me/oauth-accounts', route => route.fulfill({ json: [] }))
  let linkRequested = false
  await page.route('**/api/v1/auth/oauth/mastodon/link', async (route) => {
    linkRequested = route.request().postDataJSON().instance === 'social.example'
    await route.fulfill({ json: { authorization_url: 'http://127.0.0.1:3010/profil?mastodon_link=mocked' } })
  })

  await page.goto('/profil')
  await page.getByRole('button', { name: 'Mastodon-Konto verknüpfen' }).click()
  const dialog = page.getByRole('dialog', { name: 'Mastodon verbinden' })
  await dialog.getByLabel('Mastodon-Instanz').fill('social.example')
  await dialog.getByRole('button', { name: 'Weiter' }).click()

  await page.waitForURL(/mastodon_link=mocked/)
  expect(linkRequested).toBe(true)
  expect(page.url()).not.toContain('/login')
})
