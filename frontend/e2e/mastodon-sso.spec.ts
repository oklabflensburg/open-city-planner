import { expect, test } from '@playwright/test'

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
    await page.getByRole('button', { name: 'Mit Mastodon anmelden' }).click()
    const dialog = page.getByRole('dialog', { name: 'Mit Mastodon anmelden' })
    await expect(dialog).toBeVisible()
    const instance = dialog.getByLabel('Mastodon-Instanz')
    await expect(instance).toBeFocused()
    await expect(dialog).toContainText('Deine Zugangsdaten gibst du ausschließlich auf deiner Mastodon-Instanz ein.')
    await instance.fill('@stadtfreund@social.example')
    await dialog.getByRole('button', { name: 'Weiter' }).click()

    await page.waitForURL(/mastodon_redirect=mocked/)
    expect(postedInstance).toBe('@stadtfreund@social.example')
  })
}

test('authenticated profile starts Mastodon linking without visiting login', async ({ page }) => {
  const user = {
    id: '11111111-1111-4111-8111-111111111111',
    email: 'user@example.org',
    first_name: 'Stadt',
    last_name: 'Freund',
    display_name: 'Stadtfreund',
    avatar_url: null,
    is_active: true,
    is_verified: true,
    email_pending: false,
    is_superuser: false,
    roles: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    last_login_at: null
  }
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: { user, csrf_token: 'csrf-test' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: providers }))
  await page.route('**/api/v1/users/me/oauth-accounts', route => route.fulfill({ json: [] }))
  let linkRequested = false
  await page.route('**/api/v1/auth/oauth/mastodon/link', async (route) => {
    linkRequested = route.request().postDataJSON().instance === 'social.example'
    await route.fulfill({ json: { authorization_url: 'http://127.0.0.1:3010/profil?mastodon_link=mocked' } })
  })

  await page.goto('/profil')
  await page.getByRole('button', { name: 'Mastodon verbinden' }).click()
  const dialog = page.getByRole('dialog', { name: 'Mastodon verbinden' })
  await dialog.getByLabel('Mastodon-Instanz').fill('social.example')
  await dialog.getByRole('button', { name: 'Weiter' }).click()

  await page.waitForURL(/mastodon_link=mocked/)
  expect(linkRequested).toBe(true)
  expect(page.url()).not.toContain('/login')
})
