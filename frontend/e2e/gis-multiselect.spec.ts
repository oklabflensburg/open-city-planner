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

const vacantPolygon = {
  ...polygon,
  id: '55555555-5555-4555-8555-555555555555',
  slug: 'leerstand-testflaeche',
  name: 'Leerstehende Testfläche',
  occupancy_status: 'VACANT'
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
    const params = new URL(route.request().url()).searchParams
    const categories = params.get('categories')?.split(',')
    const statuses = params.get('occupancy_statuses')?.split(',')
    const categoryMatches = !categories || categories.includes('fashion')
    const result = !categoryMatches
      ? []
      : statuses?.length === 1 && statuses[0] === 'VACANT'
        ? [vacantPolygon]
        : !statuses || statuses.includes('OCCUPIED') ? [polygon] : []
    return route.fulfill({ json: result })
  })
  await page.route('**/api/v1/analytics/overview**', (route) => {
    const params = new URL(route.request().url()).searchParams
    const categories = params.get('categories')?.split(',')
    return route.fulfill({ json: analytics(!categories || categories.includes('fashion') ? 1 : 0) })
  })
  await page.route('**/api/v1/osm/features?**', (route) => {
    const params = new URL(route.request().url()).searchParams
    const filteredByUnsupportedSize = params.has('area_sizes')
    const requestedCategories = params.get('osm_categories')?.split(',') || []
    const features = filteredByUnsupportedSize || !requestedCategories.includes('retail') ? [] : [osmFeature]
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
  await page.route('**/api/v1/analysis-areas', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/analysis-areas/geojson', route => route.fulfill({ json: { type: 'FeatureCollection', features: [] } }))
}

function group(page: Page, title: string) {
  return page.locator('fieldset').filter({ has: page.getByText(title, { exact: true }) })
}

async function openGis(page: Page) {
  await page.goto('/')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })
}

async function keepOnlyIndustries(page: Page, selected: string[]) {
  const labels = [
    'Warenhaus', 'Mode / Bekleidung', 'Nahrungsmittel / Drogerie', 'Elektro / Technik',
    'Einrichtungsbedarf', 'Garten / Freizeit', 'Sonstige Waren', 'Gastronomie',
    'Einzelhandelsnahe Dienstleister', 'Sonstige Flächen'
  ]
  for (const label of labels.filter(item => !selected.includes(item))) {
    await page.getByRole('switch', { name: label }).click()
  }
}

test('desktop combines filters, persists URL history and resets globally', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)
  await expect(page.getByRole('heading', { name: 'Filter', exact: true })).toBeVisible({ timeout: 20_000 })

  const size = group(page, 'Verkaufsfläche')
  const floor = group(page, 'Etagen')
  await size.getByRole('button', { name: /Verkaufsfläche L:/ }).click()
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M(?:%2C|,)XL/)
  await page.waitForTimeout(250)
  await size.getByRole('button', { name: /Verkaufsfläche XL:/ }).click()
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M/)
  await page.waitForTimeout(250)

  await page.goBack()
  await expect.poll(() => new URL(page.url()).searchParams.get('area_sizes')).toBe('S,M,XL')
  await expect(size.getByRole('button', { name: /Verkaufsfläche L:/ })).toHaveAttribute('aria-pressed', 'false')
  await page.goForward()
  await expect.poll(() => new URL(page.url()).searchParams.get('area_sizes')).toBe('S,M')
  await expect(size.getByRole('button', { name: /Verkaufsfläche XL:/ })).toHaveAttribute('aria-pressed', 'false')
  await floor.getByRole('button', { name: /Etagen UG:/ }).click()
  await floor.getByRole('button', { name: /Etagen OG:/ }).click()
  await expect(floor.getByRole('button', { name: /Etagen EG:/ })).toHaveAttribute('aria-disabled', 'true')
  await floor.getByRole('button', { name: /Etagen EG:/ }).dispatchEvent('click')
  await expect(floor.getByRole('button', { name: /Etagen EG:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page).not.toHaveURL(/floors=NONE/)
  await floor.getByRole('button', { name: 'Filter aufheben' }).click()
  await expect.poll(() => new URL(page.url()).searchParams.get('floors')).toBeNull()
  await floor.getByRole('button', { name: /Etagen UG:/ }).click()
  await keepOnlyIndustries(page, ['Mode / Bekleidung', 'Gastronomie'])
  const status = group(page, 'Status')
  await status.getByRole('switch', { name: /Status Belegt:/ }).click()
  await status.getByRole('switch', { name: /Status Unbekannt:/ }).click()
  await expect(status.getByRole('switch', { name: /Status Leerstehend:/ })).toHaveAttribute('aria-disabled', 'true')

  await expect(size.getByRole('button', { name: /Verkaufsfläche S:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(size.getByRole('button', { name: /Verkaufsfläche M:/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page).toHaveURL(/area_sizes=S(?:%2C|,)M/)
  await expect(page).toHaveURL(/floors=EG(?:%2C|,)OG/)
  await expect(page).toHaveURL(/categories=fashion(?:%2C|,)gastronomy/)
  await expect(page).toHaveURL(/occupancy_statuses=VACANT/)
  await expect(page.getByText('4 aktiv', { exact: true })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Leerstand' })).toBeChecked()
  const themeColors = await page.evaluate(() => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance?.map
    return {
      fill: map?.getPaintProperty('overview-polygons-fill', 'fill-color'),
      line: map?.getPaintProperty('overview-polygons-line', 'line-color')
    }
  })
  expect(themeColors.line).toEqual(themeColors.fill)
  expect(JSON.stringify(themeColors.fill)).toContain('#10b981')
  expect(JSON.stringify(themeColors.fill)).toContain('#f43f5e')
  expect(JSON.stringify(themeColors.fill)).toContain('#94a3b8')

  await page.getByRole('switch', { name: 'Mode / Bekleidung' }).click()
  await expect(page.getByText('0 Treffer für die aktuelle Auswahl')).toBeVisible()
  await expect(page.getByText('Keine Objekte für diese Filter')).toHaveCount(0)
  await expect(page.locator('.maplibregl-canvas')).toBeVisible()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen der aktuellen Auswahl.')).toBeVisible()

  await page.getByRole('button', { name: 'Zurücksetzen', exact: true }).first().click()
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:3010\/$/)
  await expect(page.getByText(/aktiv$/)).toHaveCount(0)
  await expect(page.getByText(/1 passende OSM-Objekte im Ausschnitt/)).toBeVisible()

  const sources = group(page, 'Datenquellen')
  await sources.getByRole('switch', { name: /Datenquellen OpenStreetMap:/ }).click()
  await expect(page).toHaveURL(/sources=STADTPLANNER/)
  await expect(sources.getByRole('switch', { name: /Datenquellen OpenStreetMap:/ })).toHaveAttribute('aria-checked', 'false')
  await expect(page.getByText(/0 passende OSM-Objekte im Ausschnitt/)).toBeVisible()
  await sources.getByRole('switch', { name: /Datenquellen Stadtplaner:/ }).click()
  await expect(page).toHaveURL(/sources=NONE/)
  await expect(page.getByText('Keine Fachdatenquelle ausgewählt. Die Basiskarte bleibt sichtbar.')).toBeVisible()
  await expect(page.getByText('0 Treffer für die aktuelle Auswahl')).toHaveCount(0)
  await expect(page.locator('.maplibregl-canvas')).toBeVisible()
  await expect(sources.getByRole('button', { name: 'Alle auswählen' })).toBeVisible()
  await sources.getByRole('switch', { name: /Datenquellen Stadtplaner:/ }).click()
  await sources.getByRole('switch', { name: /Datenquellen OpenStreetMap:/ }).click()
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
  for (const value of ['S', 'M', 'L', 'XL']) {
    await expect(size.getByRole('button', { name: new RegExp(`Verkaufsfläche ${value}:`) })).toHaveAttribute('aria-pressed', 'true')
  }
  await expect(size.getByRole('button', { name: 'Alle abwählen' })).toHaveCount(0)
  await expect(floor.getByRole('button', { name: 'Alle abwählen' })).toHaveCount(0)
  await expect(status.getByRole('button', { name: 'Alle abwählen' })).toHaveCount(0)
  await expect(structure.getByRole('button', { name: 'Alle abwählen' })).toHaveCount(0)
  await expect(status.getByRole('switch', { checked: true })).toHaveCount(3)
  await expect(structure.getByRole('switch', { checked: true })).toHaveCount(3)
  await expect(industryHeader.getByRole('button', { name: 'Alle abwählen' })).toHaveCount(0)
  await expect(industries.locator('[role="switch"][aria-checked="true"]')).toHaveCount(10)
  const sources = group(page, 'Datenquellen')
  await expect(sources.getByRole('switch', { name: /Datenquellen Stadtplaner:/ })).toHaveAttribute('aria-checked', 'true')
  await expect(sources.getByRole('switch', { name: /Datenquellen OpenStreetMap:/ })).toHaveAttribute('aria-checked', 'true')
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:3010\/$/)
  await expect(page.getByText('Alle passenden Objekte werden angezeigt.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Analyse', exact: true })).toBeVisible()
})

test('legacy NONE deep links reopen Fachfacetten and preserve an empty source selection', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await page.goto('/?floors=NONE&categories=NONE&sources=NONE')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 20_000 })

  const floor = group(page, 'Etagen')
  const industries = page.getByRole('heading', { name: 'Branchen' }).locator('../..')
  await expect(floor.getByRole('button', { pressed: true })).toHaveCount(3)
  await expect(industries.getByRole('switch', { checked: true })).toHaveCount(10)
  await expect.poll(() => new URL(page.url()).searchParams.get('floors')).toBeNull()
  await expect.poll(() => new URL(page.url()).searchParams.get('categories')).toBeNull()
  await expect.poll(() => new URL(page.url()).searchParams.get('sources')).toBe('NONE')
  await expect(page.getByText('Keine Fachdatenquelle ausgewählt. Die Basiskarte bleibt sichtbar.')).toBeVisible()
  await expect(page.getByText('0 Treffer für die aktuelle Auswahl')).toHaveCount(0)
})

test('binary layer switches stay independent and the OSM master preserves its child selection', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)
  await expect(page.getByRole('heading', { name: 'Layer', exact: true })).toBeVisible()

  const layerVisibility = (layerId: string) => page.evaluate((id) => {
    const map = (window as typeof window & { __stadtplanerMapPerformance?: { map: import('maplibre-gl').Map } }).__stadtplanerMapPerformance?.map
    return map?.getLayer(id) ? map.getLayoutProperty(id, 'visibility') || 'visible' : 'missing'
  }, layerId)

  await expect.poll(() => layerVisibility('overview-polygons-fill'), { timeout: 20_000 }).toBe('visible')
  await expect.poll(() => layerVisibility('analysis-areas-municipality'), { timeout: 20_000 }).toBe('visible')

  const salesAreas = page.getByRole('switch', { name: /Verkaufsflächen anzeigen:/ })
  await salesAreas.click()
  await expect(salesAreas).toHaveAttribute('aria-checked', 'false')
  await expect.poll(() => layerVisibility('overview-polygons-fill')).toBe('none')
  await expect.poll(() => layerVisibility('analysis-areas-district')).toBe('visible')

  const municipality = page.getByRole('switch', { name: /Gemeinde anzeigen:/ })
  await municipality.click()
  await expect(municipality).toHaveAttribute('aria-checked', 'false')
  await expect.poll(() => layerVisibility('analysis-areas-municipality')).toBe('none')
  await expect.poll(() => layerVisibility('analysis-areas-district')).toBe('visible')

  const district = page.getByRole('switch', { name: /Stadtteile anzeigen:/ })
  const quarter = page.getByRole('switch', { name: /Quartiere anzeigen:/ })
  await district.click()
  await expect.poll(() => layerVisibility('analysis-areas-district')).toBe('none')
  await expect.poll(() => layerVisibility('analysis-areas-quarter')).toBe('visible')
  await quarter.click()
  await expect.poll(() => layerVisibility('analysis-areas-quarter')).toBe('none')

  const sources = group(page, 'Datenquellen')
  const osmMaster = sources.getByRole('switch', { name: /Datenquellen OpenStreetMap:/ })
  const pois = page.getByRole('switch', { name: /Orte und Einrichtungen aus OpenStreetMap anzeigen:/ })
  const areas = page.getByRole('switch', { name: /OpenStreetMap-Flächenobjekte anzeigen:/ })

  await areas.click()
  await expect(areas).toHaveAttribute('aria-checked', 'false')
  await expect(pois).toHaveAttribute('aria-checked', 'true')
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmFeatures)).toBe(1)
  await pois.click()
  await expect(areas).toHaveAttribute('aria-checked', 'false')
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmFeatures)).toBe(0)
  await pois.click()
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmFeatures)).toBe(1)
  await osmMaster.click()
  await expect(pois).toBeDisabled()
  await expect(areas).toBeDisabled()
  await expect(pois).toHaveAttribute('aria-checked', 'true')
  await expect(areas).toHaveAttribute('aria-checked', 'false')
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmFeatures)).toBe(0)

  await osmMaster.click()
  await expect(pois).toBeEnabled()
  await expect(areas).toBeEnabled()
  await expect(pois).toHaveAttribute('aria-checked', 'true')
  await expect(areas).toHaveAttribute('aria-checked', 'false')
  await expect.poll(() => page.evaluate(() => (window as typeof window & {
    __stadtplanerMapPerformance?: { snapshot: () => Record<string, number> }
  }).__stadtplanerMapPerformance?.snapshot().osmFeatures)).toBe(1)
})

test('a settled filter change performs one request and one swap per overlay', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockGis(page)
  await openGis(page)
  await expect(page.getByText(/1 passende OSM-Objekte im Ausschnitt/)).toBeVisible({ timeout: 20_000 })
  const industryHeader = page.getByRole('heading', { name: 'Branchen' }).locator('..')
  await keepOnlyIndustries(page, ['Mode / Bekleidung', 'Gastronomie'])
  await expect(page).toHaveURL(/categories=fashion(?:%2C|,)gastronomy/)
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

  await page.getByRole('switch', { name: 'Gastronomie' }).click()
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
  await size.getByRole('button', { name: /Verkaufsfläche L:/ }).click()
  await size.getByRole('button', { name: /Verkaufsfläche XL:/ }).click()
  const status = group(page, 'Status')
  await status.getByRole('switch', { name: /Status Belegt:/ }).click()
  await status.getByRole('switch', { name: /Status Unbekannt:/ }).click()
  await keepOnlyIndustries(page, ['Gastronomie'])
  await page.getByRole('button', { name: /Ergebnisse anzeigen|Keine Ergebnisse/ }).click()

  await expect(page.getByRole('button', { name: 'Filter öffnen' })).toContainText('3')
  await page.getByRole('button', { name: 'Analyse öffnen' }).click()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen der aktuellen Auswahl.')).toBeVisible()
  await page.getByRole('button', { name: 'Filter zurücksetzen', exact: true }).click()
  await expect(page.getByText('Keine gepflegten Stadtplaner-Flächen entsprechen der aktuellen Auswahl.')).toHaveCount(0)
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

    // Measure scrolling after the sheet entrance transition has settled.
    await expect.poll(async () => {
      const first = await sheetHeader.boundingBox()
      await page.waitForTimeout(80)
      const second = await sheetHeader.boundingBox()
      return Math.abs((second?.y || 0) - (first?.y || 0))
    }).toBeLessThan(1)

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
    { width: 375, height: 812 }, { width: 390, height: 844 }, { width: 393, height: 852 },
    { width: 412, height: 915 }, { width: 430, height: 932 },
    { width: 768, height: 1024 }, { width: 1024, height: 768 }, { width: 1180, height: 820 },
    { width: 1280, height: 800 }, { width: 1366, height: 768 }, { width: 1440, height: 900 },
    { width: 1920, height: 1080 }
  ]
  for (const { width, height } of viewports) {
    await page.setViewportSize({ width, height })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    if (width >= 1280) {
      await expect(page.getByRole('heading', { name: 'Filter', exact: true })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Analyse', exact: true })).toBeVisible()
      await expect(page.locator('[data-intelligent-search]:visible')).toHaveCount(1)
      await expect(page.getByRole('button', { name: 'Suche öffnen' })).toBeHidden()
    } else {
      await expect(page.locator('[data-intelligent-search]:visible')).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Suche öffnen' })).toBeVisible()
      await expect(page.getByRole('button', { name: 'Filter öffnen' })).toBeVisible()
      await expect(page.getByRole('button', { name: 'Analyse öffnen' })).toBeVisible()
      const mapBox = await page.locator('.maplibregl-map').boundingBox()
      const shellBox = await page.locator('.overview-shell').boundingBox()
      expect(mapBox).not.toBeNull()
      expect(shellBox).not.toBeNull()
      expect(mapBox!.y - shellBox!.y).toBeLessThanOrEqual(10)
    }
  }
})

test('long German switch labels and counts remain readable at narrow width and 200 percent text size', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  await mockGis(page)
  await openGis(page)
  await page.getByRole('button', { name: 'Filter öffnen' }).click()

  const dialog = page.getByRole('dialog')
  const labels = [
    'Inhabergeführt',
    'Einzelhandelsnahe Dienstleister',
    'Nahrungsmittel / Drogerie',
    'Sonstige Flächen'
  ]
  for (const label of labels) await expect(dialog.getByRole('switch', { name: label })).toBeVisible()
  await expect(dialog.getByRole('switch', { name: /^Datenquellen OpenStreetMap:/ })).toBeVisible()

  const serviceSwitch = dialog.getByRole('switch', { name: 'Einzelhandelsnahe Dienstleister' })
  await serviceSwitch.locator('span[aria-hidden="true"]').last().evaluate(element => { element.textContent = '1.234' })
  await serviceSwitch.locator('span').filter({ hasText: 'Einzelhandelsnahe Dienstleister' }).evaluate((element) => {
    element.textContent = 'Einzelhandelsnahe Dienstleistungen und sonstige Angebote'
  })
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' })

  await expect.poll(() => dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  const overflowingSwitches = await dialog.locator('[role="switch"]').evaluateAll(elements => elements.map((element) => {
    const row = element as HTMLElement
    return { name: row.getAttribute('aria-label'), clientWidth: row.clientWidth, scrollWidth: row.scrollWidth }
  }).filter(row => row.scrollWidth > row.clientWidth))
  expect(overflowingSwitches).toEqual([])
  await expect(serviceSwitch.getByText('1.234', { exact: true })).toBeVisible()
})
