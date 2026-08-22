import { expect, test, type Page } from '@playwright/test'

test.describe.configure({ timeout: 90_000 })

const filters = { categories: [], occupancy_statuses: [], floors: [], area_sizes: [], business_structures: [], sources: [] }
const areaRef = { id: 'district', slug: 'altstadt', name: 'Altstadt', area_type: 'DISTRICT' }
const area = {
  type: 'Feature' as const, id: 'district',
  geometry: { type: 'MultiPolygon' as const, coordinates: [[[[9.42, 54.77], [9.46, 54.77], [9.46, 54.81], [9.42, 54.81], [9.42, 54.77]]]] },
  properties: areaRef
}
const collection = { type: 'FeatureCollection' as const, features: [area] }

async function prepare(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { detail: 'anonymous' } }))
  await page.route('**/api/v1/auth/oauth/providers', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/polygons/overview**', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/osm/features?**', route => route.fulfill({ json: {
    type: 'FeatureCollection', features: [], meta: { count: 0, truncated: false, zoom: 16, summary: {}, canonical_summary: {}, canonical_facets: {}, business_count: 0, context_count: 0, deduplicated_linked_count: 0, osm_data_updated_at: null }
  } }))
  await page.route('**/api/v1/analysis-areas**', (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/geojson')) return route.fulfill({ json: collection })
    if (path.endsWith('/analysis-areas')) return route.fulfill({ json: [areaRef] })
    return route.fulfill({ status: 404, json: { detail: 'nicht benötigt' } })
  })
  await page.goto('/')
  await expect(page.locator('.maplibregl-map')).toBeVisible({ timeout: 30_000 })
}

function assistantResponse(query: string, values: Record<string, unknown>) {
  return {
    query, answer: values.answer || 'Antwort',
    plan: values.plan || { intent: 'ANSWER_QUESTION', steps: [], response_mode: 'ANSWER' },
    presentation: values.presentation || { type: 'TEXT', title: 'Antwort', value: null, unit: null, items: [] },
    presentation_behavior: values.presentation_behavior || undefined,
    citations: [], sources_used: [], map_actions: values.map_actions || [], warnings: [],
    context: { active_area: areaRef, active_filters: filters, last_compared_areas: [], last_intent: 'ANSWER_QUESTION', last_topic: 'POI_COUNT' },
    telemetry: { llm_used: false, model: null, tool_calls: 2, duration_ms: 3, intent: 'ANSWER_QUESTION', success: true }
  }
}

async function query(page: Page, value: string) {
  let search = page.locator('[data-intelligent-search]:visible')
  if (!await search.count()) {
    await page.getByRole('button', { name: 'Suche öffnen' }).click()
    search = page.getByRole('dialog', { name: 'Stadtplaner durchsuchen' }).locator('[data-intelligent-search]')
  }
  await search.getByPlaceholder('Stadtplaner durchsuchen…').fill(value)
  await search.getByRole('button', { name: 'Suche ausführen' }).click()
}

test('POI-Frage zeigt eine strukturierte Metrik', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Für Altstadt sind 82 POIs erfasst.',
    presentation: { type: 'METRIC', title: 'POIs in Altstadt', value: 82, unit: null, items: [] }
  }) }))
  await prepare(page)
  await query(page, 'Wie viele POIs gibt es in der Altstadt?')
  await expect(page.locator('[data-assistant-metric]')).toHaveText('82')
  const panel = await page.locator('[data-assistant-panel]').boundingBox()
  const map = await page.locator('.maplibregl-map').boundingBox()
  expect(panel && map && panel.x < map.x).toBeTruthy()
})

test('Gebietsbefehl schaltet den Stadtteil-Layer', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Es wurde 1 Gebiet gefunden.',
    plan: { intent: 'LIST_AREAS', steps: [], response_mode: 'ANSWER' },
    presentation: { type: 'AREA_LIST', title: 'Gebiete', value: null, unit: null, items: [areaRef] },
    map_actions: [{ type: 'SHOW_ANALYSIS_AREAS', area_slug: null, area_slugs: [], area_type: 'DISTRICT', fit_bounds: true, bounds: null, feature_collection: null, filters: null, geometry_filter: null }]
  }) }))
  await prepare(page)
  await query(page, 'Alle Stadtteile anzeigen')
  await expect(page.locator('[data-assistant-panel]')).toHaveCount(0)
  await expect(page.locator('[data-search-confirmation]')).toContainText('1 Gebiet')
  await expect.poll(() => page.evaluate(() => {
    const map = (window as any).__stadtplanerMapPerformance?.map
    return map?.getLayer('analysis-areas-district')
      ? map.getLayoutProperty('analysis-areas-district', 'visibility') || 'visible'
      : 'fehlt'
  })).toBe('visible')
})

test('Gastronomieflächen landen im persistenten Suchlayer', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Ich zeige 1 passendes Objekt in Altstadt.',
    plan: { intent: 'SHOW_FEATURES', steps: [], response_mode: 'ANSWER' },
    presentation: { type: 'FEATURE_LIST', title: 'Gastronomie in Altstadt', value: 1, unit: null, items: [{ name: 'Café' }] },
    map_actions: [{ type: 'REPLACE_SEARCH_LAYER', area_slug: 'altstadt', area_slugs: [], area_type: null, fit_bounds: true, bounds: [9.42, 54.77, 9.46, 54.81], feature_collection: collection, filters: { ...filters, categories: ['gastronomy'] }, geometry_filter: 'POLYGONS_ONLY' }]
  }) }))
  await prepare(page)
  await query(page, 'Gastronomieflächen in der Altstadt')
  await expect(page.locator('[data-search-layer-count="1"]')).toBeAttached()
})

test('Folgefrage aktualisiert den bestehenden Leerstandsfilter', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Die Kartenfilter wurden aktualisiert.',
    plan: { intent: 'CHANGE_FILTERS', steps: [], response_mode: 'ANSWER' },
    map_actions: [{ type: 'UPDATE_FILTERS', area_slug: null, area_slugs: [], area_type: null, fit_bounds: false, bounds: null, feature_collection: null, filters: { ...filters, occupancy_statuses: ['VACANT'] }, geometry_filter: null }]
  }) }))
  await prepare(page)
  await query(page, 'Nur Leerstände')
  await expect(page.locator('[data-assistant-panel]')).toHaveCount(0)
  await expect(page.locator('[data-search-confirmation]')).toContainText('aktualisiert')
})

test('Gebietsvergleich zeigt eine Comparison Card', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Ich habe Altstadt und Innenstadt verglichen.',
    plan: { intent: 'COMPARE_AREAS', steps: [], response_mode: 'ANSWER' },
    presentation: { type: 'COMPARISON', title: 'Gebietsvergleich', value: null, unit: null, items: [
      { name: 'Altstadt', metrics: { vacant_count: 3, polygon_count: 20, total_area_m2: 5000 } },
      { name: 'Innenstadt', metrics: { vacant_count: 8, polygon_count: 30, total_area_m2: 9000 } }
    ] }
  }) }))
  await prepare(page)
  await query(page, 'Vergleiche Altstadt und Innenstadt')
  await expect(page.locator('[data-assistant-comparison]')).toContainText('Innenstadt')
})

test('Wissensfrage zeigt eine Knowledge Card mit Datenbasis', async ({ page }) => {
  const explanation = 'amenity=restaurant wird der Kategorie Gastronomie zugeordnet.'
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: {
    ...assistantResponse((await route.request().postDataJSON()).query, {
      answer: explanation,
      presentation: { type: 'KNOWLEDGE', title: 'Gastronomie', value: null, unit: null, items: [{
        key: 'category.gastronomy', title: 'Gastronomie',
        description: explanation
      }] }
    }),
    sources_used: [{ type: 'KNOWLEDGE', area_slug: null, source: 'docs/osm-data.md', period: null, inherited_from_parent: null, knowledge_key: 'category.gastronomy' }],
    follow_up_actions: [{ type: 'SHOW_DATA_SOURCE', label: 'Datenquelle anzeigen', query: 'Welche Datenquellen kennt der Stadtplaner?' }]
  } }))
  await prepare(page)
  await query(page, 'Was bedeutet Gastronomie?')
  await expect(page.locator('[data-assistant-knowledge]')).toContainText('amenity=restaurant')
  await expect(page.getByText(explanation, { exact: true })).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Gastronomie', exact: true })).toHaveCount(1)
  await expect(page.locator('[data-assistant-follow-ups]')).toContainText('Datenquelle anzeigen')
})

test('Definition der Leerstandsquote erscheint als Knowledge Card', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Die Leerstandsquote berücksichtigt nur Flächen mit bekanntem Belegungsstatus.',
    presentation: { type: 'KNOWLEDGE', title: 'Leerstandsquote', value: null, unit: null, items: [{
      key: 'metric.vacancy_rate', title: 'Leerstandsquote',
      description: 'Die Leerstandsquote berücksichtigt nur Flächen mit bekanntem Belegungsstatus.',
      source: { type: 'CODE', path: 'backend/app/services/analytics.py' }
    }] }
  }) }))
  await prepare(page)
  await query(page, 'Was bedeutet Leerstandsquote?')
  await expect(page.locator('[data-assistant-knowledge]')).toContainText('bekanntem Belegungsstatus')
})

test('Leerstandsmetrik und Erklärung erscheinen in getrennten Ergebnisabschnitten', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Die Leerstandsquote beträgt 8,7 Prozent.',
    presentation: {
      type: 'METRIC', title: 'Leerstandsquote in Altstadt', value: 8.7, unit: '%', items: [],
      sections: [{ type: 'KNOWLEDGE', title: 'Definition', value: null, unit: null, metadata: {}, sections: [], items: [{
        key: 'metric.vacancy_rate', title: 'Leerstandsquote',
        description: 'UNKNOWN wird nicht als belegt gewertet.',
        source: { type: 'CODE', path: 'backend/app/services/analytics.py' }
      }] }]
    }
  }) }))
  await prepare(page)
  await query(page, 'Wie hoch ist die Leerstandsquote in Altstadt und was bedeutet sie?')
  await expect(page.locator('[data-assistant-metric]')).toContainText('8,7 %')
  await expect(page.locator('[data-assistant-result-section]')).toContainText('UNKNOWN')
})

test('Statistikübersicht zeigt Stand, Quelle und geerbtes Statistikgebiet', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Für Altstadt liegen kommunale Kennzahlen vor.',
    presentation: {
      type: 'STATISTICS_OVERVIEW', title: 'Statistik für Altstadt', value: null, unit: null,
      items: [{ key: 'population', name: 'Bevölkerung', value: 92000, unit: 'persons', period: '2025' }],
      metadata: {
        requested_area: areaRef, statistics_area: { ...areaRef, name: 'Flensburg' },
        inherited_from_parent: true, period: '2025', source: { name: 'Zahlenspiegel' }
      }, sections: []
    }
  }) }))
  await prepare(page)
  await query(page, 'Welche Statistiken gibt es für die Altstadt?')
  await expect(page.locator('[data-assistant-statistics]')).toContainText('92.000 Personen')
  await expect(page.locator('[data-assistant-statistics-metadata]')).toContainText('Zahlenspiegel')
  await expect(page.locator('[data-assistant-statistics-inherited]')).toContainText('übergeordneten Statistikgebiets')
})

test('Statistikzeitreihe bleibt als Tabelle im Assistant-Panel geöffnet', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Die Zeitreihe enthält zwei Berichtsperioden.',
    presentation: {
      type: 'STATISTIC_SERIES', title: 'Bevölkerung in Altstadt', value: null, unit: 'persons',
      items: [{ period: '2024', value: 91000, suppressed: false }, { period: '2025', value: 92000, suppressed: false }],
      metadata: { inherited_from_parent: false, period: '2025', source: { name: 'Zahlenspiegel' } }, sections: []
    }
  }) }))
  await prepare(page)
  await query(page, 'Wie hat sich die Bevölkerung in der Altstadt entwickelt?')
  await expect(page.locator('[data-assistant-statistic-series]')).toContainText('2024')
  await expect(page.locator('[data-assistant-statistic-series]')).toContainText('92.000 Personen')
  await expect(page.locator('[data-assistant-panel]')).toBeVisible()
})

test('Kombinierte Statistik- und Dokumentationsantwort trennt beide Abschnitte', async ({ page }) => {
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Die Bevölkerung beträgt 92.000 Personen.',
    presentation: {
      type: 'STATISTIC_METRIC', title: 'Bevölkerung in Altstadt', value: 92000, unit: 'persons',
      items: [{ key: 'population', name: 'Bevölkerung', value: 92000, unit: 'persons', period: '2025' }],
      metadata: { inherited_from_parent: false, period: '2025', source: { name: 'Zahlenspiegel' } },
      sections: [{ type: 'KNOWLEDGE', title: 'Definition und Datengrundlage', value: null, unit: null, metadata: {}, sections: [], items: [{
        key: 'statistic.population', title: 'Bevölkerung', description: 'Veröffentlichter Bevölkerungsstand je Berichtsperiode.',
        source: { type: 'DOCUMENTATION', path: 'docs/flensburg-statistics.md' }
      }] }]
    }
  }) }))
  await prepare(page)
  await query(page, 'Wie viele Einwohner hat die Altstadt und aus welcher Quelle?')
  await expect(page.locator('[data-assistant-metric]')).toContainText('92.000 Personen')
  await expect(page.locator('[data-assistant-result-section]')).toContainText('Veröffentlichter Bevölkerungsstand')
  await expect(page.getByRole('link', { name: 'Mehr anzeigen' })).toHaveAttribute('href', '/dokumentation')
})

test('Statistik-Folgefrage sendet das aktive Gebiet und die vorherige Kennzahl weiter', async ({ page }) => {
  let turn = 0
  await page.route('**/api/v1/assistant/query', async (route) => {
    const body = await route.request().postDataJSON()
    turn += 1
    if (turn === 2) {
      expect(body.context.active_area.slug).toBe('altstadt')
      expect(body.context.last_topic).toBe('STATISTICS_OVERVIEW')
    }
    return route.fulfill({ json: {
      ...assistantResponse(body.query, {
        answer: turn === 1 ? 'Für Altstadt liegen Statistiken vor.' : 'Die Bevölkerung beträgt 92.000 Personen.',
        presentation: turn === 1
          ? { type: 'STATISTICS_OVERVIEW', title: 'Statistik für Altstadt', value: null, unit: null, items: [], metadata: {}, sections: [] }
          : { type: 'STATISTIC_METRIC', title: 'Bevölkerung', value: 92000, unit: 'persons', items: [], metadata: {}, sections: [] }
      }),
      context: {
        active_area: areaRef, active_filters: filters, last_compared_areas: [],
        last_intent: 'ANSWER_QUESTION', last_topic: turn === 1 ? 'STATISTICS_OVERVIEW' : 'STATISTIC_METRIC',
        last_metric_key: turn === 1 ? null : 'population', last_source_type: 'STATISTICS',
        selected_polygon_slug: null, selected_osm_feature: null, viewport: null
      }
    } })
  })
  await prepare(page)
  await query(page, 'Welche Statistiken gibt es für Altstadt?')
  await query(page, 'Und die Bevölkerung?')
  await expect(page.locator('[data-assistant-metric]')).toContainText('92.000 Personen')
})

test('Mobile Antworten öffnen im bestehenden Bottom Sheet', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/v1/assistant/query', async route => route.fulfill({ json: assistantResponse((await route.request().postDataJSON()).query, {
    answer: 'Für Altstadt sind 82 POIs erfasst.',
    presentation: { type: 'METRIC', title: 'POIs in Altstadt', value: 82, unit: null, items: [] },
    presentation_behavior: 'KEEP_OPEN'
  }) }))
  await prepare(page)

  await expect(page.locator('[data-intelligent-search]:visible')).toHaveCount(0)
  await page.getByRole('button', { name: 'Suche öffnen' }).click()
  const searchDialog = page.getByRole('dialog', { name: 'Stadtplaner durchsuchen' })
  await expect(searchDialog.locator('[data-search-suggestions]')).toBeVisible()
  await expect(searchDialog.getByPlaceholder('Stadtplaner durchsuchen…')).toBeFocused()

  await query(page, 'Wie viele POIs gibt es in der Altstadt?')

  await expect(page.getByRole('dialog', { name: 'Stadtplaner durchsuchen' })).toBeVisible()
  await expect(page.locator('[data-assistant-metric]')).toHaveText('82')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Stadtplaner durchsuchen' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Suche öffnen' }).click()
  await expect(page.getByPlaceholder('Stadtplaner durchsuchen…')).toHaveValue('Wie viele POIs gibt es in der Altstadt?')
  await searchDialog.getByRole('button', { name: 'Verlauf' }).click()
  await expect(searchDialog.locator('[data-assistant-history]')).toContainText('Wie viele POIs gibt es in der Altstadt?')
  await page.goBack()
  await expect(searchDialog).toHaveCount(0)
  expect(new URL(page.url()).pathname).toBe('/')
})
