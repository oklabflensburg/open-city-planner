import { expect, test, type Page } from '@playwright/test'

const account = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'account@example.org',
  first_name: 'Account',
  last_name: 'Owner',
  display_name: 'Account Owner',
  avatar_url: null,
  is_active: true,
  is_verified: true,
  email_pending: false,
  is_superuser: false,
  roles: [],
  created_at: '2026-08-17T08:00:00Z',
  updated_at: '2026-08-17T08:00:00Z',
  last_login_at: '2026-08-17T08:30:00Z'
}

async function mockProfile(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    json: { user: account, csrf_token: 'playwright-csrf' }
  }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/users/me/oauth-accounts', route => route.fulfill({ json: [] }))
}

async function openProfile(page: Page) {
  const sessionLoaded = page.waitForResponse(response =>
    response.url().endsWith('/api/v1/auth/session') && response.ok()
  )
  await page.goto('/profil')
  await sessionLoaded
  await expect(page.getByText(account.email, { exact: true })).toBeVisible()
}

test('deactivation confirms once, logs out and reports success', async ({ page }) => {
  await mockProfile(page)
  let requestCount = 0
  await page.route('**/api/v1/users/me/deactivate', async (route) => {
    requestCount += 1
    await route.fulfill({ json: { message: 'Dein Konto wurde deaktiviert.' } })
  })
  await openProfile(page)

  await page.getByRole('button', { name: 'Konto deaktivieren', exact: true }).click()
  const dialog = page.getByRole('alertdialog', { name: 'Konto deaktivieren?' })
  await expect(dialog).toContainText('Deine Daten und bisherigen Beiträge bleiben erhalten.')
  await dialog.getByRole('button', { name: 'Konto deaktivieren', exact: true }).click()

  await expect(page).toHaveURL(/\/login\?account=deactivated$/)
  await expect(page.getByText('Dein Konto wurde deaktiviert.', { exact: false })).toBeVisible()
  expect(requestCount).toBe(1)
})

test('permanent deletion requires the second explicit confirmation', async ({ page }) => {
  await mockProfile(page)
  let requestBody: unknown
  await page.route('**/api/v1/users/me', async (route) => {
    if (route.request().method() !== 'DELETE') return route.continue()
    requestBody = route.request().postDataJSON()
    await route.fulfill({ json: { message: 'Dein Konto wurde dauerhaft gelöscht.' } })
  })
  await openProfile(page)

  await page.getByRole('button', { name: 'Konto dauerhaft löschen', exact: true }).click()
  const warning = page.getByRole('alertdialog', { name: 'Konto dauerhaft löschen?' })
  await expect(warning).toContainText('Diese Aktion ist endgültig.')
  await warning.getByRole('button', { name: 'Weiter' }).click()

  const confirmation = page.getByRole('alertdialog', { name: 'Löschung bestätigen' })
  const deleteButton = confirmation.getByRole('button', { name: 'Konto endgültig löschen' })
  await expect(deleteButton).toBeDisabled()
  await confirmation.getByLabel('Bestätigungstext').fill('löschen')
  await confirmation.getByLabel(/Aktuelles Passwort/).fill('current password')
  await expect(deleteButton).toBeEnabled()
  await deleteButton.click()

  await expect(page).toHaveURL(/\/login\?account=deleted$/)
  expect(requestBody).toEqual({
    confirmation_text: 'löschen',
    current_password: 'current password'
  })
})

test('danger zone and dialogs remain viewport-safe on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockProfile(page)
  await openProfile(page)
  await page.getByRole('button', { name: 'Konto dauerhaft löschen', exact: true }).click()
  await page.getByRole('alertdialog', { name: 'Konto dauerhaft löschen?' }).getByRole('button', { name: 'Weiter' }).click()

  await expect(page.getByRole('alertdialog', { name: 'Löschung bestätigen' })).toBeVisible()
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true)
})

async function mockAnonymousSession(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    status: 401,
    json: { detail: { error: { code: 'AUTH_REQUIRED', message: 'Bitte melde dich an.' } } }
  }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
}

test('password login shows the self-deactivation explanation without creating a session', async ({ page }) => {
  await mockAnonymousSession(page)
  let loginAttempts = 0
  await page.route('**/api/v1/auth/login', route => {
    loginAttempts += 1
    return route.fulfill({
      status: 403,
      json: {
        detail: {
          error: {
            code: 'ACCOUNT_SELF_DEACTIVATED',
            message: 'Dieses Konto wurde selbst deaktiviert.'
          }
        }
      }
    })
  })
  await page.goto('/login')
  await page.getByLabel('E-Mail').fill(account.email)
  await page.getByLabel('Passwort').fill('correct password')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()

  const status = page.getByRole('status').filter({ hasText: 'Dein Konto ist deaktiviert' })
  await expect(status).toContainText('Du hast dieses Konto zuvor selbst deaktiviert.')
  await expect(status.getByRole('link', { name: 'Kontakt aufnehmen' })).toBeVisible()
  await expect(page.getByText('ACCOUNT_SELF_DEACTIVATED')).toHaveCount(0)
  expect(loginAttempts).toBe(1)
})

test('Mastodon callback redirects to a readable and query-safe status on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAnonymousSession(page)
  let callbackCount = 0
  await page.route('**/api/v1/auth/oauth/mastodon/callback**', (route) => {
    callbackCount += 1
    return route.fulfill({
      status: 302,
      headers: { location: '/login?auth_error=ACCOUNT_SELF_DEACTIVATED' }
    })
  })
  await page.goto('/api/v1/auth/oauth/mastodon/callback?code=mock-code&state=mock-state')

  const status = page.getByRole('status').filter({ hasText: 'Dein Konto ist deaktiviert' })
  await expect(status).toBeVisible()
  await expect(status).toContainText('wende dich bitte an den Support')
  await expect(page.getByText('ACCOUNT_SELF_DEACTIVATED')).toHaveCount(0)
  await expect(page).toHaveURL(/\/login$/)
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true)
  expect(callbackCount).toBe(1)
})
