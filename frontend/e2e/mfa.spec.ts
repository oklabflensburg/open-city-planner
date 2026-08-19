import { expect, test, type Page } from '@playwright/test'

const user = {
  id: 'mfa-user', email: 'mfa@example.org', first_name: 'Mfa', last_name: 'User',
  display_name: 'Mfa User', avatar_url: null, is_active: true, is_verified: true,
  email_pending: false, is_superuser: false, roles: [],
  created_at: new Date().toISOString(), updated_at: new Date().toISOString(), last_login_at: null
}

async function unauthenticated(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: { error: { code: 'AUTH_REQUIRED', message: 'Bitte anmelden.' } } } }))
  await quietBackgroundApis(page)
}

async function quietBackgroundApis(page: Page) {
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/notifications**', route => route.fulfill({ json: { items: [], total: 0, unread_count: 0 } }))
  await page.route('**/api/v1/users/me/notification-subscriptions**', route => route.fulfill({ json: [] }))
}

test('password login creates an MFA step and authenticates only after TOTP', async ({ page }) => {
  await unauthenticated(page)
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: { status: 'mfa_required', challenge_token: 'opaque-challenge-token-value-1234567890', method: 'totp', expires_in: 300 } }))
  await page.route('**/api/v1/auth/mfa/verify', route => route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf-mfa' } }))

  await page.goto('/login')
  await page.getByLabel('E-Mail').fill(user.email)
  await page.getByLabel('Passwort').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Zwei-Faktor-Authentifizierung' })).toBeVisible()
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('123456')
  await page.getByRole('button', { name: 'Bestätigen' }).click()
  await expect(page).toHaveURL('/')
})

test('invalid TOTP remains logged out and recovery code can finish login', async ({ page }) => {
  await unauthenticated(page)
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: { status: 'mfa_required', challenge_token: 'opaque-challenge-token-value-1234567890', method: 'totp', expires_in: 300 } }))
  let attempts = 0
  await page.route('**/api/v1/auth/mfa/verify', async (route) => {
    attempts += 1
    if (attempts === 1) return route.fulfill({ status: 401, json: { detail: { error: { code: 'MFA_CODE_INVALID', message: 'Der eingegebene Code ist nicht gültig.' } } } })
    return route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf-recovery' } })
  })
  await page.goto('/login')
  await page.getByLabel('E-Mail').fill(user.email)
  await page.getByLabel('Passwort').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('000000')
  await page.getByRole('button', { name: 'Bestätigen' }).click()
  await expect(page.getByRole('alert')).toContainText('nicht gültig')
  await page.getByRole('button', { name: 'Wiederherstellungscode verwenden' }).click()
  await expect(page.getByText('zwölfstelligen Codes')).toBeVisible()
  await page.getByLabel('Wiederherstellungscode').fill('3223322323')
  await expect(page.getByRole('button', { name: 'Bestätigen' })).toBeDisabled()
  await page.getByLabel('Wiederherstellungscode').fill('ABCD-EFGH-JKLM')
  await page.getByRole('button', { name: 'Bestätigen' }).click()
  await expect(page).toHaveURL('/')
})

test('TOTP setup shows a local QR code and one-time recovery codes', async ({ page }) => {
  await quietBackgroundApis(page)
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf' } }))
  await page.route('**/api/v1/auth/mfa/security', route => route.fulfill({ json: { enabled: false, method: null, enabled_at: null, last_used_at: null, recovery_codes_remaining: 0 } }))
  await page.route('**/api/v1/auth/mfa/totp/setup', route => route.fulfill({ json: { secret: 'JBSWY3DPEHPK3PXP', otpauth_uri: 'otpauth://totp/Stadtplaner:mfa@example.org?secret=JBSWY3DPEHPK3PXP&issuer=Stadtplaner', issuer: 'Stadtplaner', account_name: user.email, expires_in: 600 } }))
  await page.route('**/api/v1/auth/mfa/totp/confirm', route => route.fulfill({ json: { recovery_codes: ['AAAA-BBBB-CCCC', 'DDDD-EEEE-FFFF'] } }))

  await page.goto('/profil/sicherheit')
  await page.getByRole('button', { name: 'Zwei-Faktor-Authentifizierung einrichten' }).click()
  await expect(page.getByAltText('QR-Code zur Einrichtung der Authenticator-App')).toHaveAttribute('src', /^data:image\/png/)
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('123456')
  await page.getByRole('button', { name: 'Einrichtung bestätigen' }).click()
  await expect(page.getByText('AAAA-BBBB-CCCC')).toBeVisible()
  await expect(page.getByText('Diese Liste wird nicht erneut angezeigt.')).toBeVisible()
})

test('recovery codes can be regenerated after strong confirmation', async ({ page }) => {
  await quietBackgroundApis(page)
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf' } }))
  await page.route('**/api/v1/auth/mfa/security', route => route.fulfill({ json: { enabled: true, method: 'totp', enabled_at: new Date().toISOString(), last_used_at: null, recovery_codes_remaining: 8 } }))
  await page.route('**/api/v1/auth/mfa/recovery-codes', route => route.fulfill({ json: { recovery_codes: ['NEW1-CODE-AAAA', 'NEW2-CODE-BBBB'] } }))

  await page.goto('/profil/sicherheit')
  await page.getByRole('button', { name: 'Wiederherstellungscodes erneuern' }).click()
  await page.getByLabel('Aktuelles Passwort (bei Passwortkonten)').fill('correct horse battery staple')
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('123456')
  await page.getByRole('button', { name: 'Bestätigen' }).click()
  await expect(page.getByText('NEW1-CODE-AAAA')).toBeVisible()
})

test('MFA disable requires password and factor, then returns to login', async ({ page }) => {
  let authenticated = true
  await quietBackgroundApis(page)
  await page.route('**/api/v1/auth/session', route => authenticated
    ? route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf' } })
    : route.fulfill({ status: 401, json: { detail: { error: { code: 'AUTH_REQUIRED', message: 'Bitte anmelden.' } } } }))
  await page.route('**/api/v1/auth/mfa/security', route => route.fulfill({ json: { enabled: true, method: 'totp', enabled_at: new Date().toISOString(), last_used_at: null, recovery_codes_remaining: 8 } }))
  await page.route('**/api/v1/auth/mfa/totp', async (route) => { authenticated = false; await route.fulfill({ json: { message: 'Deaktiviert.' } }) })

  await page.goto('/profil/sicherheit')
  await page.getByRole('button', { name: 'Zwei-Faktor-Authentifizierung deaktivieren' }).click()
  await page.getByLabel('Aktuelles Passwort (bei Passwortkonten)').fill('correct horse battery staple')
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('123456')
  await page.getByRole('button', { name: 'Bestätigen' }).click()
  await expect(page).toHaveURL(/\/login/)
})
