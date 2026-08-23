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
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: { status: 'mfa_required', challenge_token: 'opaque-challenge-token-value-1234567890', method: 'totp', preferred_method: 'totp', methods: ['totp'], expires_in: 300 } }))
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
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: { status: 'mfa_required', challenge_token: 'opaque-challenge-token-value-1234567890', method: 'totp', preferred_method: 'totp', methods: ['totp', 'recovery_code'], expires_in: 300 } }))
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
  await expect(page.getByText('Jeder Wiederherstellungscode kann nur einmal verwendet werden.')).toBeVisible()
  await page.getByLabel('Zwölfstelliger Wiederherstellungscode').fill('3223322323')
  await expect(page.getByRole('button', { name: 'Wiederherstellungscode bestätigen' })).toBeDisabled()
  await page.getByLabel('Zwölfstelliger Wiederherstellungscode').fill('abcd efgh ijkl')
  await page.getByRole('button', { name: 'Wiederherstellungscode bestätigen' }).click()
  await expect(page).toHaveURL('/')
})

test('cancelled passkey keeps TOTP and recovery alternatives available', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let passkeyVerifyRequests = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/api/v1/auth/mfa/passkey/verify')) passkeyVerifyRequests += 1
  })
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'credentials', {
      configurable: true,
      value: { get: async () => {
        await new Promise(resolve => setTimeout(resolve, 300))
        throw new DOMException('cancelled', 'NotAllowedError')
      } }
    })
  })
  await unauthenticated(page)
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: {
    status: 'mfa_required',
    challenge_token: 'opaque-challenge-token-value-1234567890',
    method: 'passkey',
    preferred_method: 'passkey',
    methods: ['passkey', 'totp', 'recovery_code'],
    expires_in: 300
  } }))
  await page.route('**/api/v1/auth/mfa/passkey/options', route => route.fulfill({ json: {
    ceremony_token: 'mfa-ceremony-token-value-1234567890',
    options: { challenge: 'AQID', rpId: 'localhost', allowCredentials: [] }
  } }))
  await page.route('**/api/v1/auth/mfa/verify', route => route.fulfill({ json: {
    status: 'authenticated', user, csrf_token: 'csrf-after-cancel'
  } }))

  await page.goto('/login')
  await page.getByLabel('E-Mail').fill(user.email)
  await page.getByLabel('Passwort').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await page.getByRole('button', { name: 'Passkey verwenden', exact: true }).click()

  await expect(page.getByRole('button', { name: 'Passkey wird geprüft …' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Authenticator-App verwenden' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Wiederherstellungscode verwenden' })).toBeDisabled()

  await expect(page.getByRole('status')).toContainText('Passkey-Anmeldung nicht abgeschlossen')
  await expect(page.getByRole('button', { name: 'Passkey erneut versuchen' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Authenticator-App verwenden' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Wiederherstellungscode verwenden' })).toBeVisible()
  await expect(page.getByText('Sechsstelligen Code aus Ihrer Authenticator-App eingeben')).toBeVisible()
  await expect(page.getByText('Einen gespeicherten Wiederherstellungscode verwenden')).toBeVisible()
  const methodOptions = page.locator('[data-mfa-method-option]')
  await expect(methodOptions).toHaveCount(2)
  for (const viewport of [
    { width: 375, height: 812 }, { width: 390, height: 844 },
    { width: 1280, height: 800 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }
  ]) {
    await page.setViewportSize(viewport)
    const boxes = await methodOptions.evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect()
      return { width: rect.width, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth }
    }))
    expect(boxes[0]!.width).toBeCloseTo(boxes[1]!.width, 0)
    expect(boxes.every(box => box.scrollWidth <= box.clientWidth)).toBe(true)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  }
  expect(passkeyVerifyRequests).toBe(0)

  await page.getByRole('button', { name: 'Authenticator-App verwenden' }).click()
  await expect(page.getByRole('heading', { name: 'Authenticator-App' })).toBeVisible()
  await expect(page.getByLabel('Sechsstelliger Authenticator-Code')).toBeFocused()
  await expect(page.getByRole('button', { name: 'Passkey verwenden' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Wiederherstellungscode verwenden' })).toBeVisible()
  await page.getByRole('button', { name: 'Wiederherstellungscode verwenden' }).click()
  await expect(page.getByLabel('Zwölfstelliger Wiederherstellungscode')).toBeFocused()
  await expect(page.getByRole('button', { name: 'Passkey verwenden' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Authenticator-App verwenden' })).toBeVisible()
  await page.getByRole('button', { name: 'Authenticator-App verwenden' }).click()
  await expect(page.getByLabel('Sechsstelliger Authenticator-Code')).toBeFocused()
  await page.getByLabel('Sechsstelliger Authenticator-Code').fill('123456')
  await page.getByRole('button', { name: 'Code bestätigen' }).click()
  await expect(page).toHaveURL('/')
})

test('OAuth MFA ignores URL method hints and renders only backend methods', async ({ page }) => {
  await unauthenticated(page)
  await page.route('**/api/v1/auth/mfa/challenge', route => route.fulfill({ json: {
    preferred_method: 'recovery_code',
    methods: ['recovery_code'],
    expires_in: 300
  } }))

  await page.goto('/auth/mfa?redirect=%2Fprofil&methods=passkey%2Ctotp')

  await expect(page.getByLabel('Zwölfstelliger Wiederherstellungscode')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Passkey verwenden' })).toHaveCount(0)
  await expect(page.getByLabel('Sechsstelliger Authenticator-Code')).toHaveCount(0)
  await expect(page).toHaveURL('/auth/mfa')
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

test('virtual authenticator registers, signs in, confirms MFA and removes a passkey', async ({ page, context }) => {
  test.setTimeout(60_000)
  const cdp = await context.newCDPSession(page)
  await cdp.send('WebAuthn.enable')
  await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: {
      protocol: 'ctap2',
      transport: 'internal',
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true
    }
  })
  let authenticated = true
  let registeredId = ''
  let passkeys: Array<Record<string, unknown>> = []
  const creationOptions = {
    rp: { id: 'localhost', name: 'Stadtplaner Test' },
    user: { id: 'AAAAAAAAAAAAAAAAAAAAAQ', name: user.email, displayName: 'Mfa User' },
    challenge: 'AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA',
    pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
    timeout: 60000,
    attestation: 'none',
    authenticatorSelection: { residentKey: 'required', userVerification: 'required' },
    excludeCredentials: []
  }
  const authenticationOptions = () => ({
    challenge: 'ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8',
    rpId: 'localhost',
    timeout: 60000,
    userVerification: 'required',
    allowCredentials: registeredId ? [{ type: 'public-key', id: registeredId, transports: ['internal'] }] : []
  })
  await quietBackgroundApis(page)
  await page.route('**/api/v1/auth/session', route => authenticated
    ? route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf' } })
    : route.fulfill({ status: 401, json: { detail: { error: { code: 'AUTH_REQUIRED', message: 'Bitte anmelden.' } } } }))
  await page.route('**/api/v1/auth/mfa/security', route => route.fulfill({ json: { enabled: false, method: null, enabled_at: null, last_used_at: null, recovery_codes_remaining: 0 } }))
  await page.route('**/api/v1/users/me/passkeys', async (route) => {
    return route.fulfill({ json: passkeys })
  })
  await page.route('**/api/v1/users/me/passkeys/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      passkeys = []
      return route.fulfill({ status: 204 })
    }
    return route.fulfill({ json: passkeys[0] })
  })
  await page.route('**/api/v1/auth/passkeys/register/options', route => route.fulfill({ json: { ceremony_token: 'register-ceremony-token-value-123456', options: creationOptions } }))
  await page.route('**/api/v1/auth/passkeys/register/verify', async (route) => {
    const body = route.request().postDataJSON()
    registeredId = body.credential.rawId
    passkeys = [{ id: '11111111-1111-1111-1111-111111111111', name: body.name || 'Passkey 1', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), last_used_at: null, device_type: 'single_device', backed_up: false, transports: ['internal'] }]
    return route.fulfill({ json: passkeys[0] })
  })
  await page.route('**/api/v1/auth/passkeys/login/options', route => route.fulfill({ json: { ceremony_token: 'login-ceremony-token-value-123456789', options: authenticationOptions() } }))
  await page.route('**/api/v1/auth/passkeys/login/verify', async (route) => { authenticated = true; await route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf-passkey' } }) })
  await page.route('**/api/v1/auth/passkeys/reauth/options', route => route.fulfill({ json: { ceremony_token: 'reauth-ceremony-token-value-123456', options: authenticationOptions() } }))
  await page.route('**/api/v1/auth/passkeys/reauth/verify', route => route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf-reauth' } }))
  await page.route('**/api/v1/auth/logout', async (route) => { authenticated = false; await route.fulfill({ json: { message: 'Abgemeldet.' } }) })
  await page.route('**/api/v1/auth/login', route => route.fulfill({ json: { status: 'mfa_required', challenge_token: 'opaque-challenge-token-value-1234567890', method: 'passkey', preferred_method: 'passkey', methods: ['passkey'], expires_in: 300 } }))
  await page.route('**/api/v1/auth/mfa/passkey/options', route => route.fulfill({ json: { ceremony_token: 'mfa-ceremony-token-value-1234567890', options: authenticationOptions() } }))
  await page.route('**/api/v1/auth/mfa/passkey/verify', async (route) => { authenticated = true; await route.fulfill({ json: { status: 'authenticated', user, csrf_token: 'csrf-mfa-passkey' } }) })

  await page.goto('http://localhost:3010/profil/sicherheit')
  await page.getByLabel('Name des neuen Passkeys (optional)').fill('Test-Laptop')
  await page.getByRole('button', { name: 'Passkey hinzufügen' }).click()
  await expect(page.getByRole('heading', { name: 'Test-Laptop' })).toBeVisible()

  await page.locator('[data-header-account]').click()
  await page.getByRole('menuitem', { name: 'Abmelden' }).click()
  await page.goto('http://localhost:3010/login')
  await page.getByRole('button', { name: 'Mit Passkey anmelden' }).click()
  await expect(page).toHaveURL('http://localhost:3010/')

  await page.locator('[data-header-account]').click()
  await page.getByRole('menuitem', { name: 'Abmelden' }).click()
  await page.goto('http://localhost:3010/login')
  await page.getByLabel('E-Mail').fill(user.email)
  await page.getByLabel('Passwort').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await page.getByRole('button', { name: 'Passkey verwenden' }).click()
  await expect(page).toHaveURL('http://localhost:3010/')

  await page.goto('http://localhost:3010/profil/sicherheit')
  await page.getByRole('button', { name: 'Entfernen' }).click()
  await page.getByRole('button', { name: 'Passkey entfernen', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Test-Laptop' })).toHaveCount(0)
})
