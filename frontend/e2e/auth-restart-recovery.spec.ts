import { expect, test } from '@playwright/test'

const user = {
  id: 'restart-user',
  email: 'restart@example.org',
  first_name: 'Restart',
  last_name: 'User',
  display_name: 'Restart User',
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

test('startup recovers an expired access token through one refresh without logging out', async ({ page }) => {
  let sessionRequests = 0
  let refreshRequests = 0

  await page.route('**/api/v1/auth/session', async (route) => {
    sessionRequests += 1
    if (sessionRequests === 1) {
      await route.fulfill({
        status: 401,
        json: {
          detail: {
            error: {
              code: 'ACCESS_TOKEN_EXPIRED',
              message: 'Die Zugriffssitzung muss erneuert werden.'
            }
          }
        }
      })
      return
    }
    await route.fulfill({ json: { user, csrf_token: 'csrf-after-restart' } })
  })
  await page.route('**/api/v1/auth/refresh', async (route) => {
    refreshRequests += 1
    await route.fulfill({ json: { user, csrf_token: 'csrf-after-restart' } })
  })
  await page.route('**/api/v1/notifications*', route => route.fulfill({
    json: { items: [], total: 0, unread_count: 0 }
  }))

  await page.goto('/impressum')

  await expect(page.getByRole('button', { name: /Restart User/ })).toBeVisible()
  await expect(page).not.toHaveURL(/\/login/)
  expect(sessionRequests).toBe(2)
  expect(refreshRequests).toBe(1)
})
