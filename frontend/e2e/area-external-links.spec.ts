import { expect, test, type Page } from '@playwright/test'

async function expectStructuredData(page: Page, required: string[], forbidden: string[] = []) {
  await expect.poll(async () => {
    try {
      const structuredData = (
        await page.locator('script[type="application/ld+json"]').allTextContents()
      ).join('\n')
      return required.every(value => structuredData.includes(value))
        && forbidden.every(value => !structuredData.includes(value))
    } catch (error) {
      if (error instanceof Error && error.message.includes('Execution context was destroyed')) return false
      throw error
    }
  }).toBe(true)
}

test('municipality renders its own links, sameAs and SSR HTML without Wikimedia requests', async ({ page, request }) => {
  const externalRequests: string[] = []
  page.on('request', (request) => {
    const hostname = new URL(request.url()).hostname
    if (hostname.endsWith('wikidata.org') || hostname.endsWith('wikipedia.org')) {
      externalRequests.push(request.url())
    }
  })

  await page.goto('/gebiete/flensburg-27020')
  await expect(page.getByRole('heading', { name: 'Externe Quellen' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Flensburg bei Wikipedia öffnen' }))
    .toHaveAttribute('href', 'https://de.wikipedia.org/wiki/Flensburg')
  await expect(page.getByRole('link', { name: 'Flensburg bei Wikidata öffnen' }))
    .toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q3798')
  await expectStructuredData(page, [
    '"sameAs"',
    'https://www.wikidata.org/wiki/Q3798',
    'https://de.wikipedia.org/wiki/Flensburg'
  ])
  const ssrResponse = await request.get('/gebiete/flensburg-27020')
  const ssrHtml = await ssrResponse.text()
  expect(ssrHtml).toContain('https://www.wikidata.org/wiki/Q3798')
  expect(ssrHtml).toContain('https://de.wikipedia.org/wiki/Flensburg')
  expect(externalRequests).toEqual([])
})

test('district uses its own Wikidata ID instead of its municipality parent', async ({ page }) => {
  await page.goto('/gebiete/altstadt-15630273')
  await expect(page.getByRole('link', { name: 'Altstadt bei Wikidata öffnen' }))
    .toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q16064416')
  await expectStructuredData(page, ['Q16064416'], ['Q3798'])
})

test('quarter with its own match renders that match responsively', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/gebiete/achter-de-moehl-15655762')
  await expect(page.getByRole('link', { name: 'Achter de Möhl bei Wikidata öffnen' }))
    .toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q1420075')
  const links = page.getByRole('navigation', { name: 'Externe Quellen zu Achter de Möhl' })
  await expect(links).toBeVisible()
  await expect(links.getByRole('link')).toHaveCount(2)
  const bounds = await links.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390)
})

test('unmatched quarter exposes neither links nor its parent Wikidata ID', async ({ page, request }) => {
  await page.goto('/gebiete/kreuz-15652249')
  await expect(page.getByRole('heading', { name: 'Externe Quellen' })).toHaveCount(0)
  await expectStructuredData(page, ['Kreuz'], ['"sameAs"', 'Q12329230'])
  const response = await request.get('http://127.0.0.1:8010/api/v1/analysis-areas/by-slug/kreuz-15652249')
  const detail = await response.json()
  expect(detail.external_links).toEqual({ wikidata: null, wikipedia: null })
})
