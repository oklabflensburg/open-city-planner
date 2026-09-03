import { expect, test } from '@playwright/test'

test.describe('installed Analysis Areas v1.5.2', () => {
  test('renders overview, navigation, sitemap and SSR metadata', async ({ page, request }) => {
    const response = await page.goto('/gebiete')
    expect(response?.status()).toBe(200)
    await expect(page.getByRole('heading', { level: 1, name: 'Gebiete in Flensburg' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Innenstadt Test', exact: true }).first()).toBeVisible()
    await expect(
      page.getByRole('navigation', { name: 'Hauptnavigation' })
        .getByRole('link', { name: 'Gebiete', exact: true })
    ).toBeVisible()
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'http://127.0.0.1:3010/gebiete'
    )
    const structuredData = await page.locator('script[type="application/ld+json"]').allTextContents()
    expect(structuredData.join(' ')).toContain('CollectionPage')
    expect(structuredData.join(' ')).toContain('Innenstadt Test')

    const sitemap = await request.get('/sitemap.xml')
    expect(sitemap.ok()).toBe(true)
    const xml = await sitemap.text()
    expect(xml).toContain('/gebiete</loc>')
    expect(xml).toContain('/gebiete/innenstadt-test</loc>')
  })

  test('renders detail, statistics, public links and POI navigation on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const response = await page.goto('/gebiete/innenstadt-test')
    expect(response?.status()).toBe(200)
    await expect(page.getByRole('heading', { level: 1, name: 'Innenstadt Test' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Kommunale Statistik' })).toBeVisible()
    await expect(page.getByRole('link', { name: /bei Wikidata öffnen/ })).toHaveAttribute(
      'href',
      'https://www.wikidata.org/wiki/Q12345'
    )
    await expect(page.getByRole('link', { name: /bei Wikipedia öffnen/ })).toHaveAttribute(
      'href',
      'https://de.wikipedia.org/wiki/Flensburg-Altstadt'
    )
    const poi = page.getByRole('link', { name: /Café.*auf der Karte anzeigen/ })
    await expect(poi).toBeVisible()
    await poi.click()
    await expect(page).toHaveURL(/\/karte\?.*gebiet=innenstadt-test.*osm_kategorie=cafe/)
    await expect.poll(() => page.evaluate(() =>
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
    )).toBe(true)
  })

  test('contributes visible and interactive map layers', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/karte?gebiet=innenstadt-test')
    await expect(page.getByText('Analysegebiete sind auf der Karte verfügbar.')).toBeAttached()
    const districtToggle = page.getByRole('checkbox', { name: 'Stadtteile anzeigen' })
    await expect(districtToggle).toBeVisible()
    await expect(districtToggle).toBeChecked()
    await districtToggle.uncheck()
    await expect(districtToggle).not.toBeChecked()
    await districtToggle.check()
    await expect(districtToggle).toBeChecked()
  })
})
