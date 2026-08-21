import { createPinia, setActivePinia } from 'pinia'
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAnalysisAreasStore } from '~/stores/analysisAreas'
import { useFilterStore } from '~/stores/filter'
import { useMapStore } from '~/stores/map'
import { useOsmViewportStore } from '~/stores/osmViewport'
import { useSearchStore } from '~/stores/search'
import type { AssistantResponse } from '~/types/search'
import { getMapViewportPadding } from '~/utils/mapViewportPadding'

const filters = {
  categories: [], occupancy_statuses: [], floors: [], area_sizes: [],
  business_structures: [], sources: []
}

function response(overrides: Partial<AssistantResponse> = {}): AssistantResponse {
  return {
    query: 'Nur Leerstände',
    answer: 'Die Kartenfilter wurden aktualisiert.',
    plan: { intent: 'CHANGE_FILTERS', steps: [], response_mode: 'ANSWER' },
    presentation: { type: 'TEXT', title: 'Filter', value: null, unit: null, items: [] },
    presentation_behavior: 'AUTO_CLOSE',
    citations: [], sources_used: [], warnings: [],
    map_actions: [{
      type: 'UPDATE_FILTERS', area_slug: null, area_slugs: [], area_type: null,
      fit_bounds: false, bounds: null, feature_collection: null,
      filters: { ...filters, occupancy_statuses: ['VACANT'] }, geometry_filter: null
    }],
    context: {
      active_area: null, active_filters: { ...filters, occupancy_statuses: ['VACANT'] },
      last_compared_areas: [], last_intent: 'CHANGE_FILTERS', last_topic: 'FILTER'
    },
    telemetry: { llm_used: false, model: null, tool_calls: 0, duration_ms: 2, intent: 'CHANGE_FILTERS', success: true },
    ...overrides
  }
}

describe('Stadtplaner-Assistent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('useFilterStore', useFilterStore)
    vi.stubGlobal('useOsmViewportStore', useOsmViewportStore)
    vi.stubGlobal('useAnalysisAreasStore', useAnalysisAreasStore)
    vi.stubGlobal('useMapStore', useMapStore)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sendet Anfrage und expliziten Conversation Context', async () => {
    const request = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('useApi', () => ({ request }))
    const search = useSearchStore()

    await search.submit('  Nur Leerstände  ')

    expect(request).toHaveBeenCalledWith('/assistant/query', {
      method: 'POST',
      body: JSON.stringify({ query: 'Nur Leerstände', context: {
        active_area: null, active_filters: filters, last_compared_areas: [],
        last_intent: null, last_topic: null, last_metric_key: null,
        last_source_type: null, selected_polygon_slug: null,
        selected_osm_feature: null, viewport: null
      } }),
      signal: expect.any(AbortSignal), retryOnUnauthorized: false
    })
    expect(useFilterStore().occupancyStatuses).toEqual(['VACANT'])
    expect(search.context.last_topic).toBe('FILTER')
    expect(search.assistantOpen).toBe(false)
    expect(search.confirmation).toBe('Die Kartenfilter wurden aktualisiert.')
  })

  it('baut den Request-Kontext aus den tatsächlich sichtbaren Filtern auf', async () => {
    const request = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('useApi', () => ({ request }))
    const filter = useFilterStore()
    filter.setCategories(['gastronomy'])
    filter.setOccupancyStatuses(['VACANT'])
    const search = useSearchStore()
    search.context.active_filters = filters

    await search.submit('Zeige passende Flächen')

    const body = JSON.parse(request.mock.calls[0][1].body)
    expect(body.context.active_filters.categories).toEqual(['gastronomy'])
    expect(body.context.active_filters.occupancy_statuses).toEqual(['VACANT'])
  })

  it('wendet mehrere typisierte Kartenaktionen an', async () => {
    const featureCollection = { type: 'FeatureCollection' as const, features: [{
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [9.43, 54.78] },
      properties: { name: 'Café' }
    }] }
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockResolvedValue(response({
      plan: { intent: 'SHOW_FEATURES', steps: [], response_mode: 'ANSWER' },
      map_actions: [
        { type: 'FIT_AREA', area_slug: 'altstadt', area_slugs: [], area_type: null, fit_bounds: true, bounds: [9.4, 54.7, 9.5, 54.8], feature_collection: null, filters: null, geometry_filter: null },
        { type: 'REPLACE_SEARCH_LAYER', area_slug: 'altstadt', area_slugs: [], area_type: null, fit_bounds: true, bounds: [9.4, 54.7, 9.5, 54.8], feature_collection: featureCollection, filters, geometry_filter: 'POINTS_ONLY' }
      ]
    })) }))

    await useSearchStore().submit('Gastronomie in der Altstadt')

    expect(useMapStore().searchAction?.data?.features).toHaveLength(1)
    expect(useMapStore().searchActionGeneration).toBe(2)
    expect(useOsmViewportStore().showPois).toBe(true)
    expect(useOsmViewportStore().showAreas).toBe(false)
  })

  it('zeigt API-Fehler an, ohne den Kontext zu verändern', async () => {
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockRejectedValue(new Error('Gebiet unbekannt')) }))
    const search = useSearchStore()
    const before = JSON.stringify(search.context)

    await search.submit('Zeige Atlantis')

    expect(search.error).toBe('Gebiet unbekannt')
    expect(JSON.stringify(search.context)).toBe(before)
    expect(search.assistantOpen).toBe(true)
  })

  it('entfernt einen veralteten zu langen Topic-Wert vor der nächsten Anfrage', async () => {
    const request = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('useApi', () => ({ request }))
    const search = useSearchStore()
    search.context.last_topic = 'Diese Frage benötigt die erweiterte Sprachinterpretation, die derzeit nicht aktiviert ist.'

    await search.submit('Rathaus')

    expect(JSON.parse(request.mock.calls[0][1].body).context.last_topic).toBeNull()
  })

  it('gibt eine festhängende Suche nach dem Timeout für einen neuen Versuch frei', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('useApi', () => ({ request: vi.fn((_path, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Abgebrochen', 'AbortError')))
    })) }))
    const search = useSearchStore()

    const pending = search.submit('Rathaus')
    expect(search.loading).toBe(true)

    await vi.advanceTimersByTimeAsync(12_000)
    await pending

    expect(search.loading).toBe(false)
    expect(search.error).toBe('Die Suche dauert zu lange. Bitte versuchen Sie es erneut.')
  })

  it('bricht eine laufende Anfrage beim Schließen des Panels ab', async () => {
    let requestSignal!: AbortSignal
    vi.stubGlobal('useApi', () => ({ request: vi.fn((_path, options) => new Promise((_resolve, reject) => {
      requestSignal = options.signal
      options.signal.addEventListener('abort', () => reject(new DOMException('Abgebrochen', 'AbortError')))
    })) }))
    const search = useSearchStore()

    const pending = search.submit('Laufende Suche')
    search.closeAssistant()
    await pending

    expect(requestSignal.aborted).toBe(true)
    expect(search.loading).toBe(false)
    expect(search.assistantOpen).toBe(false)
  })

  it('verwirft eine verspätete Antwort der vorherigen Anfrage', async () => {
    let resolveFirst!: (value: AssistantResponse) => void
    const first = new Promise<AssistantResponse>(resolve => { resolveFirst = resolve })
    const request = vi.fn()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(response({
        query: 'Zweite Suche', answer: 'Zweite Antwort', presentation_behavior: 'KEEP_OPEN'
      }))
    vi.stubGlobal('useApi', () => ({ request }))
    const search = useSearchStore()

    const pendingFirst = search.submit('Erste Suche')
    await search.submit('Zweite Suche')
    resolveFirst(response({ query: 'Erste Suche', answer: 'Veraltete Antwort' }))
    await pendingFirst

    expect(search.result?.query).toBe('Zweite Suche')
    expect(search.result?.answer).toBe('Zweite Antwort')
  })

  it('hält erklärende Antworten offen und übernimmt leere Filter als vollständige Auswahl', async () => {
    const filter = useFilterStore()
    filter.setCategories(['gastronomy'])
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockResolvedValue(response({
      plan: { intent: 'ANSWER_QUESTION', steps: [], response_mode: 'ANSWER' },
      presentation_behavior: 'KEEP_OPEN',
      map_actions: [{
        type: 'UPDATE_FILTERS', area_slug: null, area_slugs: [], area_type: null,
        fit_bounds: false, bounds: null, feature_collection: null, filters, geometry_filter: null
      }]
    })) }))

    const search = useSearchStore()
    await search.submit('Was zählt als Gastronomie?')

    expect(search.assistantOpen).toBe(true)
    expect(filter.allCategoriesActive).toBe(true)
  })

  it('berechnet den Karteninnenabstand abhängig von Desktop- und Mobile-Panels', () => {
    expect(getMapViewportPadding({ viewportWidth: 1440, assistantOpen: true, mobilePanelOpen: false, analysisPanelVisible: true }).left).toBe(56)
    expect(getMapViewportPadding({ viewportWidth: 390, assistantOpen: true, mobilePanelOpen: true, analysisPanelVisible: false }).bottom).toBe(300)
  })

  it('rendert Knowledge, Datenquellen, Rückfragen und typisierte Folgeaktionen', () => {
    const component = readFileSync(
      new URL('../app/components/search/IntelligentSearch.vue', import.meta.url), 'utf8'
    )

    expect(component).toContain("presentation.type === 'KNOWLEDGE'")
    expect(component).toContain("presentation.type !== 'KNOWLEDGE' || !search.result.presentation.items.length")
    expect(component).toContain('knowledgeItemTitle(item)')
    expect(component).toContain("presentation.type === 'DATA_SOURCE_STATUS'")
    expect(component).toContain('data-assistant-clarification')
    expect(component).toContain('data-assistant-follow-ups')
    expect(component).toContain("presentation.type === 'STATISTICS_OVERVIEW'")
    expect(component).toContain("presentation.type === 'STATISTIC_SERIES'")
    expect(component).toContain('data-assistant-statistics-metadata')
    expect(component).toContain('data-assistant-result-section')
    expect(component).toContain("'docs/flensburg-statistics.md'")
    expect(component).toContain('Quelle: Stadtplaner-Dokumentation')
    expect(component).not.toContain('return `${label}: ${String(source.path)}`')
    expect(component).not.toContain(':disabled="search.loading')
    const shell = readFileSync(new URL('../app/components/layout/AppShell.vue', import.meta.url), 'utf8')
    expect(shell).toContain('<IntelligentSearch v-if="!isDesktop" compact @open="openAssistant" />')
    expect(shell).toContain("data-assistant-open")
  })
})
