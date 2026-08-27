import { expect, test } from '@playwright/test'
import { e2eAccountEmail, expireAccessToken, loginAs } from './support/auth'

test('authenticated session survives profile navigation and reload', async ({ page }) => {
  await loginAs(page)

  await page.goto('/profil')
  await expect(page.getByText(e2eAccountEmail(), { exact: true })).toBeVisible()
  await expect(page).toHaveURL('/profil')

  await page.reload()
  await expect(page.getByText(e2eAccountEmail(), { exact: true })).toBeVisible()
  await expect(page).toHaveURL('/profil')
})

test('startup recovers an expired access token through one real refresh without logging out', async ({ page, context }) => {
  await loginAs(page)
  await expireAccessToken(context)

  let sessionRequests = 0
  let refreshRequests = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/api/v1/auth/session')) sessionRequests += 1
    if (request.url().endsWith('/api/v1/auth/refresh')) refreshRequests += 1
  })

  await page.goto('/profil')

  await expect(page.getByText(e2eAccountEmail(), { exact: true })).toBeVisible()
  await expect(page).toHaveURL('/profil')
  expect(sessionRequests).toBe(2)
  expect(refreshRequests).toBe(1)
})
