import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 60_000 })

const areas = [
  area('flensburg', 'Flensburg', 'MUNICIPALITY', null, 56_700_000),
  area('innenstadt', 'Innenstadt', 'DISTRICT', 'Flensburg', 1_100_000),
  area('neustadt', 'Neustadt', 'DISTRICT', 'Flensburg', 1_600_000),
  area('juerde', 'Jürgensby', 'DISTRICT', 'Flensburg', 2_100_000),
  area('suedermarkt', 'Südermarkt', 'QUARTER', 'Innenstadt', 210_000)
]

const values: Record<string, { count: number, vacant: number }> = {
  flensburg: { count: 50, vacant: 10 },
  innenstadt: { count: 14, vacant: 2 },
  neustadt: { count: 7, vacant: 3 },
  juerde: { count: 4, vacant: 0 },
  suedermarkt: { count: 3, vacant: 1 }
}

function area(slug: string, name: string, areaType: string, parentName: string | null, areaM2: number) {
  return {
    id: `${slug}-id`, slug, name, area_type: areaType, parent_id: parentName ? 'parent-id' : null,
    parent_name: parentName, parent_slug: parentName?.toLowerCase() || null, area_m2: areaM2,
    source: 'OSM', source_osm_type: 'relation', source_osm_id: 1, source_admin_level: 10,
    source_place: null, source_updated_at: null, updated_at: '2026-08-18T08:00:00Z', child_count: 0,
    external_links: { wikidata: null, wikipedia: null }
  }
}

function comparisonItem(slug: string) {
  const selected = areas.find(candidate => candidate.slug === slug)!
  const metric = values[slug]
  return {
    id: selected.id, slug, name: selected.name, area_type: selected.area_type,
    parent_name: selected.parent_name, area_m2: selected.area_m2,
    metrics: {
      polygon_count: metric.count, occupied_count: metric.count - metric.vacant,
      vacant_count: metric.vacant, chain_count: 2, independent_count: Math.max(metric.count - 2, 0),
      total_area_m2: metric.count * 120, average_area_m2: 120, median_area_m2: 100,
      vacancy_rate: metric.count ? metric.vacant / metric.count * 100 : null,
      chain_store_rate: metric.count ? 20 : null, known_occupancy_count: metric.count,
      known_business_structure_count: metric.count, data_updated_at: '2026-08-18T08:00:00Z',
      locations_per_km2: metric.count / (selected.area_m2 / 1_000_000),
      retail_area_m2_per_km2: metric.count * 120 / (selected.area_m2 / 1_000_000)
    }
  }
}

async function mockComparison(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/analysis-areas', route => route.fulfill({ json: areas }))
  await page.route('**/api/v1/analytics/compare', async route => {
    const payload = route.request().postDataJSON() as { area_slugs: string[], include_municipality_benchmark: boolean }
    await route.fulfill({ json: {
      areas: payload.area_slugs.map(comparisonItem),
      benchmark: payload.include_municipality_benchmark ? comparisonItem('flensburg') : null,
      ignored_slugs: [], calculation: 'CALCULATED', source: 'Erfasste Stadtplaner-Flächen'
    } })
  })
}

test('selects concrete areas, renders distinct metrics and restores the URL', async ({ page }) => {
  await mockComparison(page)
  await page.goto('/vergleich')
  await expect(page.getByRole('heading', { name: 'Welche Gebiete möchten Sie vergleichen?' })).toBeVisible()

  await page.getByRole('button', { name: /^Innenstadt / }).click()
  await expect(page.getByRole('heading', { name: 'Vergleichspartner' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Innenstadt/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Flensburg/ })).toBeVisible()
  await expect(page).toHaveURL(/gebiete=innenstadt/)

  await page.getByRole('button', { name: /^Neustadt / }).click()
  await expect(page.getByRole('columnheader', { name: /Neustadt/ })).toBeVisible()
  const polygonRow = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Erfasste Flächen' }) })
  await expect(polygonRow).toContainText('14')
  await expect(polygonRow).toContainText('7')
  await expect(polygonRow).toContainText('50')
  await expect(page).toHaveURL(/gebiete=innenstadt(?:%2C|,)neustadt/)

  await page.reload()
  await expect(page.getByRole('columnheader', { name: /Innenstadt/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Neustadt/ })).toBeVisible()
  await expect(page.getByText('Aktuelle Auswahl', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: /^Jürgensby / }).click()
  await page.getByRole('button', { name: /^Südermarkt / }).click()
  await expect(page.getByText('Maximal 4 Gebiete können verglichen werden.')).toBeVisible()
  await expect(page.getByRole('searchbox', { name: 'Gebiet hinzufügen' })).toBeDisabled()
  await page.getByRole('button', { name: 'Neustadt aus Vergleich entfernen' }).click()
  await expect(page.getByRole('searchbox', { name: 'Gebiet hinzufügen' })).toBeEnabled()
  await expect(page).not.toHaveURL(/neustadt/)
})

test('mobile comparison keeps wide data inside its own scroll container', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockComparison(page)
  await page.goto('/vergleich?gebiete=innenstadt,neustadt,suedermarkt&benchmark=0')
  await expect(page.getByRole('heading', { name: 'Kennzahlen' })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('switch', { name: /Gesamtstadt als Referenz anzeigen/ })).toHaveAttribute('aria-checked', 'false')
  await expect(page.locator('canvas')).toHaveCount(2)
  for (const viewport of [
    { width: 320, height: 568 }, { width: 360, height: 800 }, { width: 390, height: 844 },
    { width: 430, height: 932 }, { width: 768, height: 1024 }, { width: 1024, height: 768 },
    { width: 1280, height: 800 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }
  ]) {
    await page.setViewportSize(viewport)
    const overflow = await page.evaluate(() => ({
      pageWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      elements: [...document.querySelectorAll<HTMLElement>('body *')]
        .filter(element => element.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
        .slice(0, 8)
        .map(element => ({ tag: element.tagName, className: element.className, right: Math.round(element.getBoundingClientRect().right) }))
    }))
    expect(overflow, `${viewport.width}x${viewport.height}: ${JSON.stringify(overflow)}`).toMatchObject({ pageWidth: overflow.viewportWidth })
  }
})
