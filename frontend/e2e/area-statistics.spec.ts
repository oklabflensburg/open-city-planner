import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  page.on('request', (request) => {
    expect(new URL(request.url()).hostname).not.toBe('superset.flensburg.de')
  })
})

test('municipality renders imported statistics in SSR-visible HTML', async ({ page }) => {
  await page.goto('/gebiete/flensburg-27020')
  await expect(page.getByRole('heading', { name: 'Kommunale Statistik' })).toBeVisible()
  await expect(page.getByText('98.040', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Stadt Flensburg – Zahlenspiegel')).toBeVisible()
  await expect(page.getByText('2025', { exact: true }).first()).toBeVisible()
})

test('district renders its own value and municipality comparison', async ({ page }) => {
  await page.goto('/gebiete/altstadt-15630273')
  await expect(page.getByText('3.657', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/rechnerischen Gesamtstadtwert/).first()).toBeVisible()
  await expect(page.getByRole('table')).toContainText('2020')
  await expect(page.getByRole('table')).toContainText('2025')
})

test('quarter labels inherited district statistics on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/gebiete/nordertor-15651154')
  await expect(page.getByText(/keine eigenen Zahlenspiegel-Werte/)).toBeVisible()
  await expect(page.getByText('Stadtteilwert · Altstadt')).toBeVisible()
  await expect(page.getByText('3.657', { exact: true }).first()).toBeVisible()
})
