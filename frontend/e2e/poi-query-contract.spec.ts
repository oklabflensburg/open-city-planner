import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 900 } })

test.describe('fachneutraler POI-Query-Vertrag', () => {
  test('wendet Deep Link, Änderung, Reload, Entfernen und Browser-History auf die Karte an', async ({ page }) => {
    const viewportQueries: URL[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/osm/features?')) viewportQueries.push(new URL(request.url()))
    })

    await page.goto('/karte?poi=cafe')

    await expect(page).toHaveURL(/\/karte\?poi=cafe/)
    await expect(page.getByText('POI-Kategorie: Cafés')).toBeVisible({ timeout: 15_000 })
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['cafe'])
    expect(viewportQueries.some(url => url.searchParams.get('poi') === 'cafe')).toBe(true)

    await page.reload()
    await expect(page.getByText('POI-Kategorie: Cafés')).toBeVisible({ timeout: 15_000 })
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['cafe'])

    await page.evaluate(() => {
      window.history.pushState({}, '', '/karte?poi=restaurant')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    await expect(page).toHaveURL(/\/karte\?poi=restaurant/)
    await expect(page.getByText('POI-Kategorie: Restaurants')).toBeVisible()
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['restaurant'])

    await page.getByRole('button', { name: 'Entfernen' }).click()
    await expect.poll(() => new URL(page.url()).searchParams.has('poi')).toBe(false)
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['cafe', 'restaurant'])

    await page.goBack()
    await expect(page).toHaveURL(/\/karte\?poi=restaurant/)
    await expect.poll(() => renderedPoiTypes(page)).toEqual(['restaurant'])
  })
})

async function renderedPoiTypes(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const map = window.__stadtplanerMapPerformance?.map
    if (!map?.getSource('osm-pois')) return []
    return map.querySourceFeatures('osm-pois')
      .map(feature => String(feature.properties.primary_type || ''))
      .filter(Boolean)
      .sort()
  })
}
