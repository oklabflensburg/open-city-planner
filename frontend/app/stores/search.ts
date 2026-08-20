import { defineStore } from 'pinia'
import type { AssistantContext, AssistantMapAction, AssistantResponse, SearchFilters } from '~/types/search'
import { BUSINESS_STRUCTURE_OPTIONS, DATA_SOURCE_OPTIONS, FLOOR_OPTIONS, OCCUPANCY_OPTIONS, SALES_AREA_SIZE_OPTIONS } from '~/utils/gisFilters'
import { industries } from '~/utils/industries'

let activeRequest: AbortController | null = null
let confirmationTimer: ReturnType<typeof setTimeout> | null = null
const SEARCH_TIMEOUT_MS = 12_000

type SearchHistoryEntry = {
  id: number
  query: string
  result: AssistantResponse
}

const emptyFilters = (): SearchFilters => ({
  categories: [], occupancy_statuses: [], floors: [], area_sizes: [],
  business_structures: [], sources: []
})

const emptyContext = (): AssistantContext => ({
  active_area: null,
  active_filters: emptyFilters(),
  last_compared_areas: [],
  last_intent: null,
  last_topic: null,
  selected_polygon_slug: null,
  selected_osm_feature: null,
  viewport: null
})

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: '',
    loading: false,
    error: null as string | null,
    result: null as AssistantResponse | null,
    context: emptyContext(),
    assistantOpen: false,
    activeTab: 'answer' as 'answer' | 'history',
    confirmation: null as string | null,
    history: [] as SearchHistoryEntry[],
    historySequence: 0
  }),
  actions: {
    async submit(rawQuery: string) {
      const query = rawQuery.trim()
      if (query.length < 2) return
      this.query = query
      activeRequest?.abort()
      const controller = new AbortController()
      activeRequest = controller
      let timedOut = false
      const timeout = setTimeout(() => {
        timedOut = true
        controller.abort()
      }, SEARCH_TIMEOUT_MS)
      this.loading = true
      this.error = null
      this.confirmation = null
      this.activeTab = 'answer'
      this.assistantOpen = true
      try {
        if (this.context.last_topic && this.context.last_topic.length > 50) {
          this.context.last_topic = null
        }
        const result = await useApi().request<AssistantResponse>('/assistant/query', {
          method: 'POST',
          body: JSON.stringify({ query, context: this.context }),
          signal: controller.signal,
          retryOnUnauthorized: false
        })
        if (activeRequest !== controller) return
        this.result = result
        this.context = result.context
        this.apply(result)
        this.addHistory(query, result)
        if (presentationBehavior(result) !== 'KEEP_OPEN') {
          this.assistantOpen = false
          this.showConfirmation(result.answer)
        } else {
          this.assistantOpen = true
        }
      } catch (error) {
        if (controller.signal.aborted) {
          if (timedOut && activeRequest === controller) {
            this.error = 'Die Suche dauert zu lange. Bitte versuchen Sie es erneut.'
          }
          return
        }
        this.error = error instanceof Error ? error.message : 'Die Suche konnte nicht ausgeführt werden.'
        this.assistantOpen = true
      } finally {
        clearTimeout(timeout)
        if (activeRequest === controller) {
          activeRequest = null
          this.loading = false
        }
      }
    },
    apply(result: AssistantResponse) {
      const area = result.context.active_area
      const selected = useMapStore().selectedMapEntity
      if (area && (selected?.type !== 'analysis-area' || selected.id !== area.id)) {
        useMapStore().selectedMapEntity = { type: 'analysis-area', id: area.id }
        void useAnalysisAreasStore().loadDetails(area.id)
      }
      for (const action of result.map_actions) this.applyMapAction(action)
    },
    applyMapAction(action: AssistantMapAction) {
      if (action.filters) this.applyFilters(action.filters)
      const osm = useOsmViewportStore()
      if (action.geometry_filter === 'POLYGONS_ONLY') {
        osm.showPois = false
        osm.showAreas = true
      } else if (action.geometry_filter === 'POINTS_ONLY') {
        osm.showPois = true
        osm.showAreas = false
      }
      if (action.type === 'SHOW_ANALYSIS_AREAS' && action.area_type) {
        const areas = useAnalysisAreasStore()
        areas.visibility = {
          MUNICIPALITY: action.area_type === 'MUNICIPALITY',
          DISTRICT: action.area_type === 'DISTRICT',
          QUARTER: action.area_type === 'QUARTER'
        }
      }
      useMapStore().applySearchAction(action, action.feature_collection)
    },
    applyFilters(values: SearchFilters) {
      const filter = useFilterStore()
      filter.setCategories(values.categories.length
        ? values.categories.filter(value => industries.some(item => item.key === value))
        : industries.map(item => item.key))
      filter.setOccupancyStatuses(values.occupancy_statuses.length
        ? values.occupancy_statuses.filter(value => OCCUPANCY_OPTIONS.some(item => item.value === value))
        : OCCUPANCY_OPTIONS.map(item => item.value))
      filter.setFloors(values.floors.length
        ? values.floors.filter(value => FLOOR_OPTIONS.some(item => item.value === value))
        : FLOOR_OPTIONS.map(item => item.value))
      filter.setSizes(values.area_sizes.length
        ? values.area_sizes.filter(value => SALES_AREA_SIZE_OPTIONS.some(item => item.value === value))
        : SALES_AREA_SIZE_OPTIONS.map(item => item.value))
      filter.setBusinessStructures(values.business_structures.length
        ? values.business_structures.filter(value => BUSINESS_STRUCTURE_OPTIONS.some(item => item.value === value))
        : BUSINESS_STRUCTURE_OPTIONS.map(item => item.value))
      filter.setSources(values.sources.length
        ? values.sources.filter(value => DATA_SOURCE_OPTIONS.some(item => item.value === value))
        : DATA_SOURCE_OPTIONS.map(item => item.value))
    },
    addHistory(query: string, result: AssistantResponse) {
      this.historySequence += 1
      this.history = [
        { id: this.historySequence, query, result },
        ...this.history.filter(entry => entry.query !== query)
      ].slice(0, 10)
    },
    restoreHistory(entry: SearchHistoryEntry) {
      this.query = entry.query
      this.result = entry.result
      this.context = entry.result.context
      this.activeTab = 'answer'
      this.assistantOpen = true
    },
    openAssistant() {
      if (this.result || this.error || this.loading) this.assistantOpen = true
    },
    closeAssistant() {
      activeRequest?.abort()
      activeRequest = null
      this.loading = false
      this.assistantOpen = false
      this.activeTab = 'answer'
    },
    clearQuery() {
      this.query = ''
    },
    showConfirmation(message: string) {
      if (confirmationTimer) clearTimeout(confirmationTimer)
      this.confirmation = message
      confirmationTimer = setTimeout(() => {
        this.confirmation = null
        confirmationTimer = null
      }, 5_000)
    },
    dispose() {
      activeRequest?.abort()
      activeRequest = null
      if (confirmationTimer) clearTimeout(confirmationTimer)
      confirmationTimer = null
      this.loading = false
    }
  }
})

function presentationBehavior(result: AssistantResponse) {
  if (result.presentation_behavior) return result.presentation_behavior
  if (result.plan.response_mode !== 'ANSWER') return 'KEEP_OPEN'
  if (result.plan.intent === 'CHANGE_FILTERS' || result.plan.intent === 'LIST_AREAS') return 'AUTO_CLOSE'
  return 'KEEP_OPEN'
}
