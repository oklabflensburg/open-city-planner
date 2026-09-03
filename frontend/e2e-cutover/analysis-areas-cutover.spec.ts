import { expect, test } from '@playwright/test'

test.describe('installed Analysis Areas v1.5.3', () => {
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
    await page.waitForFunction(() => Boolean(
      (document.querySelector('#__nuxt') as HTMLElement & { __vue_app__?: unknown })?.__vue_app__
    ))
    const viewportResponse = page.waitForResponse(response => {
      const url = new URL(response.url())
      return url.pathname === '/api/v1/osm/features' && url.searchParams.get('poi') === 'cafe'
    })
    await poi.click()
    await expect.poll(() => new URL(page.url()).searchParams.get('gebiet')).toBe('innenstadt-test')
    await expect.poll(() => new URL(page.url()).searchParams.get('poi')).toBe('cafe')
    const retiredQueryKey = ['osm', 'kategorie'].join('_')
    expect(new URL(page.url()).searchParams.has(retiredQueryKey)).toBe(false)

    const backendResult = await (await viewportResponse).json() as {
      features: Array<{ properties: { primary_type?: string | null } }>
    }
    expect(backendResult.features.length).toBeGreaterThan(0)
    expect(backendResult.features.every(feature => feature.properties.primary_type === 'cafe')).toBe(true)
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['cafe'])
    await expect.poll(() => page.evaluate(() =>
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
    )).toBe(true)
  })

  test('contributes visible and interactive map layers', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto('/karte?gebiet=innenstadt-test')
    await expect(page.getByText('Analysegebiete sind auf der Karte verfügbar.')).toBeAttached()
    await expect(page.locator('[data-gis-layout]')).toHaveAttribute('data-gis-layout', 'compact')
    await page.getByRole('button', { name: 'Filter öffnen' }).click()
    const districtToggle = page.getByRole('checkbox', { name: 'Stadtteile anzeigen' })
    await expect(districtToggle).toBeVisible()
    await expect(districtToggle).toBeChecked()
    await districtToggle.uncheck()
    await expect(districtToggle).not.toBeChecked()
    await districtToggle.check()
    await expect(districtToggle).toBeChecked()
  })
})

async function renderedPoiTypes(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const map = window.__stadtplanerMapPerformance?.map
    if (!map?.getSource('osm-pois')) return []
    return [...new Set(map.querySourceFeatures('osm-pois')
      .map(feature => String(feature.properties.primary_type || ''))
      .filter(Boolean))]
      .sort()
  })
}
