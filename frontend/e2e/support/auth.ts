import { createHmac, randomUUID } from 'node:crypto'
import type { BrowserContext, Page } from '@playwright/test'

export type E2EAccount = 'account' | 'admin'

type AuthSession = {
  csrf_token: string
  user: {
    email: string
    display_name: string | null
    is_superuser: boolean
  }
}

const accounts: Record<E2EAccount, { email: string, password: string }> = {
  account: {
    email: 'account@example.org',
    password: 'playwright-test-password'
  },
  admin: {
    email: 'admin@example.org',
    password: 'playwright-test-password'
  }
}

const apiBaseUrl = process.env.NUXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010/api/v1'
const e2eJwtSecret = 'playwright-e2e-jwt-signing-key-32-bytes'
const e2eJwtIssuer = 'http://127.0.0.1:8010'
const accountIds: Record<E2EAccount, string> = {
  account: '33333333-3333-4333-8333-333333333333',
  admin: '22222222-2222-4222-8222-222222222222'
}

export async function loginAs(page: Page, account: E2EAccount = 'account'): Promise<AuthSession> {
  const credentials = accounts[account]
  const response = await page.request.post(`${apiBaseUrl}/auth/login`, {
    data: { ...credentials, remember: true },
    headers: { Origin: 'http://127.0.0.1:3010' }
  })

  if (!response.ok()) {
    throw new Error(`E2E login for ${credentials.email} failed with ${response.status()}: ${await response.text()}`)
  }

  const session = await response.json() as AuthSession
  if (!session.user || !session.csrf_token) {
    throw new Error(`E2E login for ${credentials.email} did not establish an authenticated session.`)
  }
  return session
}

export const e2eAccountEmail = (account: E2EAccount = 'account') => accounts[account].email

export async function expireAccessToken(context: BrowserContext, account: E2EAccount = 'account') {
  const current = (await context.cookies()).find(cookie => cookie.name === 'ocm_access_token')
  if (!current) throw new Error('Cannot expire an E2E access token before login.')

  const now = Math.floor(Date.now() / 1000)
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')
  const payload = Buffer.from(JSON.stringify({
    sub: accountIds[account],
    type: 'access',
    iat: now - 120,
    exp: now - 60,
    jti: randomUUID(),
    iss: e2eJwtIssuer,
    aud: 'stadtplaner'
  })).toString('base64url')
  const signature = createHmac('sha256', e2eJwtSecret)
    .update(`${header}.${payload}`)
    .digest('base64url')

  await context.addCookies([{
    ...current,
    value: `${header}.${payload}.${signature}`,
    expires: now + 3_600
  }])
}
