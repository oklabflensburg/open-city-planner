import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 60_000 })

const polygon = {
  id: '44444444-4444-4444-8444-444444444444',
  slug: 'testflaeche',
  name: 'Testfläche',
  category: 'fashion',
  floor: 'EG',
  area_size: 'S',
  address_display_name: 'Flensburg',
  occupancy_status: 'OCCUPIED',
  business_structure: 'INDEPENDENT',
  geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]] },
  created_at: '2026-08-17T08:00:00Z',
  updated_at: '2026-08-17T08:00:00Z'
}

const osmFeature = {
  type: 'Feature', id: 'node/123', geometry: { type: 'Point', coordinates: [9.432, 54.784] },
  properties: {
    feature_id: 'node/123', osm_type: 'node', osm_id: 123, category: 'retail',
    canonical_category: 'fashion', name: 'OSM Mode', primary_type: 'clothes', natural: null,
    feature_type: 'point', source: 'OSM', canonical_floor: 'EG', mapped_area_m2: null,
    occupancy_status: 'UNKNOWN', occupancy_source: null, stadtplaner: []
  }
}

function analytics(count: number) {
  return {
    fast_facts: {
      shops: count,
      polygon_count: count,
      total_area_m2: count ? 120 : null,
      average_area_m2: count ? 120 : null,
      calculated_vacancy_rate: count ? 0 : null,
      calculated_chain_store_rate: count ? 0 : null,
      known_occupancy_count: count,
      known_business_structure_count: count,
      data_updated_at: '2026-08-17T08:00:00Z',
      vacancy_rate: null,
      chain_store_rate: null,
      centrality_index: null,
      purchasing_power_index: null,
      reference_date: null,
      source: null,
      updated_at: null
    },
    industry_distribution: count ? [{ category: 'fashion', count }] : [],
    category_counts: [{ category: 'fashion', count }],
    prime_rents: { unit: 'EUR_PER_SQM', period: null, rows: [] }
  }
}

async function mockGis(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/polygons/overview**', (route) => {
    const vacant = new URL(route.request().url()).searchParams.get('occupancy_statuses') === 'VACANT'
    return route.fulfill({ json: vacant ? [] : [polygon] })
  })
  await page.route('**/api/v1/analytics/overview**', (route) => {
    const vacant = new URL(route.request().url()).searchParams.get('occupancy_statuses') === 'VACANT'
    return route.fulfill({ json: analytics(vacant ? 0 : 1) })
  })
  await page.route('**/api/v1/osm/features?**', (route) => {
    const params = new URL(route.request().url()).searchParams
    const filteredByUnsupportedSize = params.has('area_sizes')
    const features = filteredByUnsupportedSize ? [] : [osmFeature]
    return route.fulfill({ json: {
      type: 'FeatureCollection', features,
      meta: {
        count: features.length, summary: features.length ? { retail: 1 } : {},
        canonical_summary: features.length ? { fashion: 1 } : {},
        canonical_facets: features.length ? { fashion: 1 } : {},
        business_count: features.length, context_count: 0, deduplicated_linked_count: 0,
        truncated: false, zoom: 17, osm_data_updated_at: '2026-08-17T08:00:00Z'
      }
    } })
  })
}

function group(page: Page, title: string) {
  return page.locator('fieldset').filter({ has: page.getByText(title, { exact: true }) })
}

async function openGis(page: Page) {
  await page.goto('/')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
}

test('desktop combines filters, persists URL history and resets globally', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)
  await expect(page.getByRole('heading', { name: 'Filter', exact: true })).toBeVisible({ timeout: 20_000 })

  const size = group(page, 'Verkaufsfläche')
  const floor = group(page, 'Etagen')
  await size.getByRole('button', { name: /Verkaufsfläche S:/ }).click()
  await expect(page).toHaveURL(/area_sizes=S/)
  await size.getByRole('button', { name: /Verkaufsfläche M:/ }).click()
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M/)

  await page.goBack()
  await expect.poll(() => new URL(page.url()).searchParams.get('area_sizes')).toBe('S')
  await expect(size.getByRole('button', { name: /Verkaufsfläche M:/ })).toHaveAttribute('aria-pressed', 'false')

  await size.getByRole('button', { name: /Verkaufsfläche M:/ }).click()
  await floor.getByRole('button', { name: /Etagen EG:/ }).click()
  await floor.getByRole('button', { name: /Etagen OG:/ }).click()
  await page.getByRole('checkbox', { name: 'Mode / Bekleidung' }).click()
  await page.getByRole('checkbox', { name: 'Gastronomie' }).click()
  await group(page, 'Status').getByRole('button', { name: /Status Leerstehend:/ }).click()

  await expect(size.getByRole('button', { name: /Verkaufsfläche S:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(size.getByRole('button', { name: /Verkaufsfläche M:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M/)
  await expect(page).toHaveURL(/floors=EG(?:%2C|,)OG/)
  await expect(page).toHaveURL(/categories=fashion(?:%2C|,)gastronomy/)
  await expect(page).toHaveURL(/occupancy_statuses=VACANT/)
  await expect(page.getByText('4 aktiv', { exact: true })).toBeVisible()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen deiner Auswahl.')).toBeVisible()

  await page.getByRole('button', { name: 'Zurücksetzen', exact: true }).first().click()
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:3010\/$/)
  await expect(page.getByText(/aktiv$/)).toHaveCount(0)
  await expect(page.getByText(/1 passende OSM-Objekte im Ausschnitt/)).toBeVisible()

  const sources = group(page, 'Datenquellen')
  await sources.getByRole('button', { name: /Datenquellen OpenStreetMap:/ }).click()
  await expect(page).toHaveURL(/sources=STADTPLANNER/)
  await expect(sources.getByRole('button', { name: /Datenquellen OpenStreetMap:/ })).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByText(/0 passende OSM-Objekte im Ausschnitt/)).toBeVisible()
  await sources.getByRole('button', { name: /Datenquellen OpenStreetMap:/ }).click()
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:3010\/$/)
})

test('all-select remains visually selected while API semantics stay unrestricted', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)

  const size = group(page, 'Verkaufsfläche')
  const floor = group(page, 'Etagen')
  const status = group(page, 'Status')
  const structure = group(page, 'Betriebsform')
  const industryHeader = page.getByRole('heading', { name: 'Branchen' }).locator('..')
  const industries = industryHeader.locator('..')
  await size.getByRole('button', { name: 'Alle auswählen' }).click()
  await floor.getByRole('button', { name: 'Alle auswählen' }).click()
  await industryHeader.getByRole('button', { name: 'Alle auswählen' }).click()
  await status.getByRole('button', { name: 'Alle auswählen' }).click()
  await structure.getByRole('button', { name: 'Alle auswählen' }).click()
  for (const value of ['S', 'M', 'L', 'XL']) {
    await expect(size.getByRole('button', { name: new RegExp(`Verkaufsfläche ${value}:`) })).toHaveAttribute('aria-pressed', 'true')
  }
  await expect(floor.getByRole('button', { name: 'Auswahl aufheben' })).toBeVisible()
  await expect(status.getByRole('button', { name: 'Auswahl aufheben' })).toBeVisible()
  await expect(structure.getByRole('button', { name: 'Auswahl aufheben' })).toBeVisible()
  await expect(industries.locator('[role="checkbox"][aria-checked="true"]')).toHaveCount(10)
  const sources = group(page, 'Datenquellen')
  await expect(sources.getByRole('button', { name: /Datenquellen Stadtplaner:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(sources.getByRole('button', { name: /Datenquellen OpenStreetMap:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M(?:%2C|,)L(?:%2C|,)XL/)
  await expect(page.getByRole('heading', { name: 'Analyse', exact: true })).toBeVisible()
})

test('a settled filter change performs one request and one swap per overlay', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)
  await expect(page.getByText(/1 passende OSM-Objekte im Ausschnitt/)).toBeVisible()
  await page.waitForTimeout(300)

  const requests = { polygons: 0, osm: 0, analytics: 0 }
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.endsWith('/polygons/overview')) requests.polygons += 1
    if (path.endsWith('/osm/features')) requests.osm += 1
    if (path.endsWith('/analytics/overview')) requests.analytics += 1
  })
  await page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { reset: () => void }
  }).__stadtplanerMapPerformance?.reset())

  await page.getByRole('checkbox', { name: 'Mode / Bekleidung' }).click()
  await expect(page).toHaveURL(/categories=fashion/)
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().polygonSetDataCalls || 0)).toBe(1)
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmSetDataCalls || 0)).toBe(2)
  await expect.poll(() => requests).toEqual({ polygons: 1, osm: 1, analytics: 1 })
  await page.waitForTimeout(350)
  expect(requests).toEqual({ polygons: 1, osm: 1, analytics: 1 })
})

test('mobile multi-select, zero-result recovery and analysis share one responsive shell', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockGis(page)
  await openGis(page)
  await page.getByRole('button', { name: 'Filter öffnen' }).click()

  const size = group(page, 'Verkaufsfläche')
  await size.getByRole('button', { name: /Verkaufsfläche S:/ }).click()
  await size.getByRole('button', { name: /Verkaufsfläche M:/ }).click()
  await group(page, 'Status').getByRole('button', { name: /Status Leerstehend:/ }).click()
  await page.getByRole('button', { name: /Ergebnisse anzeigen|Keine Ergebnisse/ }).click()

  await expect(page.getByRole('button', { name: 'Filter öffnen' })).toContainText('2')
  await page.getByRole('button', { name: 'Analyse öffnen' }).click()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen deiner Auswahl.')).toBeVisible()
  await page.getByRole('button', { name: 'Filter zurücksetzen' }).click()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen deiner Auswahl.')).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('mobile filter and analysis summaries scroll below the single sheet header', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockGis(page)
  await openGis(page)

  for (const panel of [
    { open: 'Filter öffnen', title: 'Filter', close: 'Filter schließen', summary: '[data-filter-summary]' },
    { open: 'Analyse öffnen', title: 'Analyse', close: 'Analyse schließen', summary: '[data-analysis-summary]' }
  ]) {
    await page.getByRole('button', { name: panel.open }).click()
    const dialog = page.getByRole('dialog')
    const sheetHeader = dialog.locator(':scope > header')
    const scroller = dialog.locator('[data-sheet-scroll]')
    const summary = dialog.locator(panel.summary)
    await expect(dialog.getByRole('heading', { name: panel.title, exact: true })).toHaveCount(1)
    await expect(summary).toBeVisible()

    const headerBefore = await sheetHeader.boundingBox()
    const summaryBefore = await summary.boundingBox()
    await scroller.evaluate(element => { element.scrollTop = 500 })
    await expect.poll(() => scroller.evaluate(element => element.scrollTop)).toBeGreaterThan(100)
    const headerAfter = await sheetHeader.boundingBox()
    const summaryAfter = await summary.boundingBox()

    expect(headerBefore).not.toBeNull()
    expect(headerAfter).not.toBeNull()
    expect(summaryBefore).not.toBeNull()
    expect(summaryAfter).not.toBeNull()
    expect(Math.abs((headerAfter?.y || 0) - (headerBefore?.y || 0))).toBeLessThan(2)
    expect(summaryAfter!.y).toBeLessThan(summaryBefore!.y - 100)
    await expect.poll(() => dialog.evaluate((element) => {
      return [...element.querySelectorAll<HTMLElement>('*')].filter((child) => {
        const overflow = getComputedStyle(child).overflowY
        return (overflow === 'auto' || overflow === 'scroll') && child.scrollHeight > child.clientHeight
      }).length
    })).toBe(1)

    await page.getByRole('button', { name: panel.close }).click()
    await expect(dialog).toHaveCount(0)
  }
})

test('GIS shell has no body overflow from small mobile through wide desktop', async ({ page }) => {
  await mockGis(page)
  await page.setViewportSize({ width: 320, height: 720 })
  await openGis(page)

  const viewports = [
    { width: 320, height: 568 }, { width: 360, height: 800 },
    { width: 390, height: 844 }, { width: 393, height: 852 },
    { width: 412, height: 915 }, { width: 430, height: 932 },
    { width: 768, height: 1024 }, { width: 1024, height: 768 },
    { width: 1280, height: 800 }, { width: 1440, height: 900 },
    { width: 1920, height: 1080 }
  ]
  for (const { width, height } of viewports) {
    await page.setViewportSize({ width, height })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    if (width >= 1280) {
      await expect(page.getByRole('heading', { name: 'Filter', exact: true })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Analyse', exact: true })).toBeVisible()
    } else {
      await expect(page.getByRole('button', { name: 'Filter öffnen' })).toBeVisible()
      await expect(page.getByRole('button', { name: 'Analyse öffnen' })).toBeVisible()
    }
  }
})
