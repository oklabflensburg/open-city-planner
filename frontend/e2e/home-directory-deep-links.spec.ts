import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 90_000 })

async function ignorePreviewRendering(page: Page) {
  await page.route('**/preview.webp?**', route => route.fulfill({ status: 204 }))
}

async function proxyBackendApi(page: Page) {
  await page.route('**/api/v1/**', async route => {
    try {
      const response = await route.fetch()
      const body = await response.body()
      await route.fulfill({
        status: response.status(),
        body,
        headers: {
          'content-type': response.headers()['content-type'] || 'application/json',
          'access-control-allow-origin': 'http://127.0.0.1:3010',
          'access-control-allow-credentials': 'true'
        }
      })
    } catch {
      // Navigation can dispose nonessential background requests during teardown.
    }
  })
}

async function waitForHydration(page: Page) {
  await page.waitForFunction(() => Boolean((document.querySelector('#__nuxt') as HTMLElement & { __vue_app__?: unknown })?.__vue_app__))
  await page.waitForLoadState('networkidle')
}

test('opens a homepage polygon in the existing map selection UI', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await proxyBackendApi(page)
  await ignorePreviewRendering(page)
  await page.goto('/')
  await waitForHydration(page)
  const card = page.locator('section[aria-labelledby="polygons-heading"] article').first()
  await expect(card).toBeVisible()
  const name = (await card.getByRole('heading').textContent())?.trim()
  const mapLink = card.getByRole('link', { name: 'Auf der Karte anzeigen' })
  const href = await mapLink.getAttribute('href')
  expect(name).toBeTruthy()
  expect(href).toMatch(/^\/karte\?flaeche=[a-z0-9-]+$/)
  await mapLink.click()

  await expect(page).toHaveURL(url => `${url.pathname}${url.search}` === href)
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('Ausgewählte Fläche', { exact: true }).first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('heading', { name: name! }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Details anzeigen' }).first()).toHaveAttribute('href', href!.replace('/karte?flaeche=', '/flaechen/'))
})

test('opens a homepage district in the existing area selection UI', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await proxyBackendApi(page)
  await ignorePreviewRendering(page)
  await page.goto('/')
  await waitForHydration(page)
  const card = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Altstadt' }) })
  await expect(card).toBeVisible()
  await card.getByRole('link', { name: 'Auf der Karte anzeigen' }).click()

  await expect(page).toHaveURL(/\/karte\?gebiet=altstadt-15630273$/)
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('heading', { name: 'Altstadt' }).last()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('link', { name: 'Gebiet ausführlich ansehen' }).last()).toHaveAttribute('href', '/gebiete/altstadt-15630273')
})

test('keeps the server-rendered directory free of horizontal overflow', async ({ page }) => {
  await ignorePreviewRendering(page)
  await page.goto('/')
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  }
})
