<template>
  <section
    class="overview-shell relative min-h-0 min-w-0 overflow-hidden bg-[var(--c-surface)] text-[var(--c-text)] xl:grid xl:gap-4 xl:p-4"
    :data-social-preview-capture="socialPreview ? '' : undefined"
    :data-assistant-open="isDesktop && searchStore.assistantOpen ? 'true' : 'false'"
  >
    <div class="hidden min-h-0 min-w-0 xl:block">
      <ClientOnly>
        <LazyLeftSidebar v-if="isDesktop" />
      </ClientOnly>
    </div>

    <section class="absolute inset-0 min-h-0 min-w-0 p-2 xl:relative xl:inset-auto xl:p-0" aria-label="Stadtplaner-Karte">
      <LazyMapCanvas hydrate-on-idle />
      <div class="absolute inset-x-3 top-3 z-30 xl:hidden">
        <IntelligentSearch v-if="!isDesktop" compact @open="openAssistant" />
      </div>

      <nav
        v-if="mapStore.activeMobilePanel === null"
        class="absolute bottom-[calc(env(safe-area-inset-bottom)+2.25rem)] left-1/2 z-20 grid max-w-[calc(100%-1rem)] -translate-x-1/2 grid-flow-col auto-cols-max gap-1.5 rounded-2xl border border-slate-200 bg-white/95 p-1.5 shadow-xl backdrop-blur xl:hidden"
        aria-label="Kartenaktionen"
      >
        <button class="map-action" :class="{ 'map-action-active': mapStore.activeMobilePanel === 'filter' }" type="button" aria-label="Filter öffnen" :aria-pressed="mapStore.activeMobilePanel === 'filter'" @click="openFilter">
          <span class="relative">
            <ListFilter class="size-4" aria-hidden="true" />
            <span v-if="activeFilterCount" class="absolute -right-2.5 -top-2.5 grid size-4 place-items-center rounded-full bg-white text-[9px] font-black text-[#154d73]">{{ activeFilterCount }}</span>
          </span>
          <span>Filter</span>
        </button>
        <button class="map-action" :class="{ 'map-action-active': mapStore.activeMobilePanel === 'analytics' }" type="button" aria-label="Analyse öffnen" :aria-pressed="mapStore.activeMobilePanel === 'analytics'" @click="openAnalysis">
          <BarChart3 class="size-4" aria-hidden="true" />
          <span>Analyse</span>
        </button>
        <ClientOnly>
          <NuxtLink v-if="authStore.authenticated" class="map-action map-action-primary" to="/flaechen/neu" aria-label="Neue Fläche anlegen">
            <Plus class="size-4" aria-hidden="true" />
            <span>Neue Fläche</span>
          </NuxtLink>
        </ClientOnly>
      </nav>
    </section>

    <div class="hidden min-h-0 min-w-0 xl:block">
      <ClientOnly>
        <LazyRightSidebar v-if="isDesktop" />
      </ClientOnly>
    </div>

    <AppBottomSheet
      :open="mapStore.activeMobilePanel !== null"
      :title="activePanelTitle"
      :close-label="activePanelCloseLabel"
      :content-key="activePanelContentKey"
      initial-snap="medium"
      @update:open="handleSheetOpen"
    >
      <template v-if="mapStore.activeMobilePanel === 'filter'">
        <LazyLeftSidebar embedded />
        <div class="mt-3 grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <button class="min-h-11 cursor-pointer rounded-xl border border-slate-300 px-3 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="resetFilters">Zurücksetzen</button>
          <button class="min-h-11 cursor-pointer rounded-xl bg-[#154d73] px-3 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="closeMobilePanel">{{ mobileResultLabel }}</button>
        </div>
      </template>
      <IntelligentSearch v-else-if="mapStore.activeMobilePanel === 'assistant'" embedded />
      <LazyRightSidebar v-else-if="mapStore.activeMobilePanel === 'analytics'" embedded />
      <div v-else-if="mapStore.activeMobilePanel === 'selection'" class="-m-3 min-h-full bg-white p-4">
        <MapSelectionContent embedded />
      </div>
    </AppBottomSheet>
  </section>
</template>

<script setup lang="ts">
import { BarChart3, ListFilter, Plus } from 'lucide-vue-next'

const mapStore = useMapStore()
const searchStore = useSearchStore()
const route = useRoute()
const socialPreview = computed(() => route.query['social-preview'] === '1')
const filterStore = useFilterStore()
const analyticsStore = useAnalyticsStore()
const osmStore = useOsmViewportStore()
const analysisAreasStore = useAnalysisAreasStore()
const authStore = useAuthStore()
const mapSelection = useMapSelection()
useGisFilterHistory()
const isDesktop = ref(false)
const activeFilterCount = computed(() => filterStore.activeFilterCount + (osmStore.areaPoiFilter ? 1 : 0))
const mobileResultCount = computed(() => usePolygonStore().polygons.length
  + (osmStore.areaPoiFilter ? osmStore.data?.meta.count || 0 : osmStore.data?.meta.business_count || 0))
const mobileResultLabel = computed(() => mobileResultCount.value ? `${mobileResultCount.value} Ergebnisse anzeigen` : 'Keine Ergebnisse')
const activePanelTitle = computed(() => {
  if (mapStore.activeMobilePanel === 'assistant') return 'Stadtplaner durchsuchen'
  if (mapStore.activeMobilePanel === 'filter') return activeFilterCount.value ? `Filter · ${activeFilterCount.value} aktiv` : 'Filter'
  if (mapStore.activeMobilePanel === 'selection' && mapStore.selectedMapEntity?.type === 'polygon') return 'Ausgewählte Fläche'
  if (osmStore.selectedFeature) return 'OpenStreetMap-Objekt'
  if (analysisAreasStore.selectedArea) return analysisAreasStore.selectedArea.name
  return 'Analyse'
})
const activePanelCloseLabel = computed(() => {
  if (mapStore.activeMobilePanel === 'assistant') return 'Assistant schließen'
  if (mapStore.activeMobilePanel === 'filter') return 'Filter schließen'
  if (mapStore.activeMobilePanel === 'selection') return 'Auswahl schließen'
  return 'Analyse schließen'
})
const activePanelContentKey = computed(() => {
  const entity = mapStore.selectedMapEntity
  if (mapStore.activeMobilePanel !== 'selection' || !entity) return mapStore.activeMobilePanel || 'closed'
  if (entity.type === 'polygon') return `polygon:${entity.id}`
  if (entity.type === 'osm') return `osm:${entity.feature.properties.osm_type}:${entity.feature.properties.osm_id}`
  return `analysis-area:${entity.id}`
})

let analyticsTimer: ReturnType<typeof setTimeout> | undefined
let desktopQuery: MediaQueryList | undefined
let panelHistoryActive = false
let closingFromHistory = false

onMounted(() => {
  mapStore.closeMobilePanels()
  desktopQuery = window.matchMedia('(min-width: 1280px)')
  isDesktop.value = desktopQuery.matches
  if (isDesktop.value) void analyticsStore.load()
  desktopQuery.addEventListener('change', handleDesktopBreakpoint)
  window.addEventListener('popstate', handlePopState)
})

watch(() => mapStore.activeMobilePanel, (panel, previous) => {
  if (!import.meta.client) return
  if (panel && !previous) {
    window.history.pushState({ ...window.history.state, mobileGisPanel: true }, '')
    panelHistoryActive = true
  } else if (!panel && previous && panelHistoryActive && !closingFromHistory) {
    panelHistoryActive = false
    const state = { ...window.history.state }
    delete state.mobileGisPanel
    window.history.replaceState(state, '')
  }
})

watch(() => searchStore.assistantOpen, (open) => {
  if (!import.meta.client || isDesktop.value) return
  if (open) mapStore.openMobilePanel('assistant')
  else if (mapStore.activeMobilePanel === 'assistant') mapStore.closeMobilePanel()
})

watch(
  () => filterStore.filterKey,
  () => {
    if (!analyticsIsVisible()) return
    clearTimeout(analyticsTimer)
    analyticsTimer = setTimeout(() => analyticsStore.load(), 180)
    if (analysisAreasStore.selectedAreaId) void analysisAreasStore.loadDetails()
  }
)

watch(() => analysisAreasStore.selectedAreaId, () => {
  if (!analyticsIsVisible()) return
  clearTimeout(analyticsTimer)
  analyticsTimer = setTimeout(() => analyticsStore.load(), 80)
})

onBeforeUnmount(() => {
  clearTimeout(analyticsTimer)
  panelHistoryActive = false
  mapStore.closeMobilePanels()
  mapSelection.clearSelection()
  searchStore.dispose()
  desktopQuery?.removeEventListener('change', handleDesktopBreakpoint)
  window.removeEventListener('popstate', handlePopState)
})

function openFilter() {
  mapStore.openMobilePanel('filter')
}

function openAnalysis() {
  mapStore.openMobilePanel('analytics')
  void analyticsStore.load()
}

function openAssistant() {
  searchStore.openAssistant()
  mapStore.openMobilePanel('assistant')
}

function handleSheetOpen(open: boolean) {
  if (!open) closeMobilePanel()
}

function closeMobilePanel() {
  if (mapStore.activeMobilePanel === 'selection') mapSelection.clearSelection()
  if (mapStore.activeMobilePanel === 'assistant') searchStore.closeAssistant()
  mapStore.closeMobilePanel()
}

function resetFilters() {
  filterStore.reset()
  osmStore.reset()
}

function handleDesktopBreakpoint(event: MediaQueryListEvent) {
  isDesktop.value = event.matches
  if (event.matches) void analyticsStore.load()
  if (event.matches) mapStore.closeMobilePanel()
  else if (searchStore.assistantOpen) mapStore.openMobilePanel('assistant')
}

function analyticsIsVisible() {
  return isDesktop.value || mapStore.activeMobilePanel === 'analytics'
}

function handlePopState() {
  if (!panelHistoryActive || !mapStore.activeMobilePanel) return
  panelHistoryActive = false
  closingFromHistory = true
  if (mapStore.activeMobilePanel === 'selection') mapSelection.clearSelection()
  mapStore.closeMobilePanel()
  nextTick(() => { closingFromHistory = false })
}
</script>

<style scoped>
.overview-shell {
  height: calc(100vh - 4rem);
}

.map-action {
  display: inline-flex;
  height: 2.75rem;
  min-width: 2.75rem;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  padding-inline: 0.65rem;
  color: #334155;
  font-size: 0.75rem;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 150ms, border-color 150ms, color 150ms, box-shadow 150ms;
  white-space: nowrap;
}

.map-action:hover { background: #f1f5f9; }
.map-action-active { border-color: #8baabd; background: #e2edf4; color: #154d73; }
.map-action:focus-visible { outline: 2px solid #154d73; outline-offset: 2px; }
.map-action-primary { border-color: #154d73; background: #154d73; color: white; }
.map-action-primary:hover { background: #0f3f61; }


@supports (height: 100dvh) {
  .overview-shell { height: calc(100dvh - 4rem); }
}

@media (min-width: 1280px) {
  .overview-shell {
    min-height: 620px;
    grid-template-columns: 272px minmax(0, 1fr) 312px;
  }

  .overview-shell[data-assistant-open='true'] {
    grid-template-columns: minmax(380px, 400px) minmax(0, 1fr) 312px;
  }
}

@media (min-width: 1440px) {
  .overview-shell { grid-template-columns: 288px minmax(600px, 1fr) 328px; }
  .overview-shell[data-assistant-open='true'] { grid-template-columns: 420px minmax(600px, 1fr) 328px; }
}
</style>
