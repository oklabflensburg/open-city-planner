<template>
  <section
    class="overview-shell relative min-h-0 min-w-0 overflow-hidden bg-[var(--c-surface)] text-[var(--c-text)]"
    :data-social-preview-capture="socialPreview ? '' : undefined"
    :data-assistant-open="isDesktop && searchStore.assistantOpen ? 'true' : 'false'"
    :data-compact-panel-open="isCompact && mapStore.activeGisPanel !== null ? 'true' : 'false'"
    :data-gis-layout="isDesktop ? 'desktop' : isCompact ? 'compact' : 'mobile'"
  >
    <div class="hidden min-h-0 min-w-0 xl:block">
      <ClientOnly><LazyLeftSidebar v-if="isDesktop" /></ClientOnly>
    </div>

    <section class="gis-map-stage absolute inset-0 min-h-0 min-w-0 p-2 xl:relative xl:inset-auto xl:p-0" aria-label="Stadtplaner-Karte" data-gis-map-stage>
      <LazyMapCanvas />
      <nav
        v-if="mapStore.activeGisPanel === null || isCompact"
        class="mobile-map-actions absolute left-1/2 z-20 -translate-x-1/2 rounded-2xl border border-slate-200 bg-white/95 p-1.5 shadow-xl backdrop-blur xl:hidden"
        aria-label="Kartenaktionen"
        data-mobile-map-actions
      >
        <button class="map-action" :class="{ 'map-action-active': mapStore.activeGisPanel === 'assistant' }" type="button" aria-label="Suche öffnen" :aria-pressed="mapStore.activeGisPanel === 'assistant'" @click="openSearch">
          <Search class="size-4" aria-hidden="true" /><span>Suche</span>
        </button>
        <button class="map-action" :class="{ 'map-action-active': mapStore.activeGisPanel === 'filter' }" type="button" aria-label="Filter öffnen" :aria-pressed="mapStore.activeGisPanel === 'filter'" @click="openFilter">
          <span class="relative"><ListFilter class="size-4" aria-hidden="true" /><span v-if="activeFilterCount" class="absolute -right-2.5 -top-2.5 grid size-4 place-items-center rounded-full bg-white text-[9px] font-black text-[#154d73]">{{ activeFilterCount }}</span></span>
          <span>Filter</span>
        </button>
        <button class="map-action" :class="{ 'map-action-active': mapStore.activeGisPanel === 'analytics' }" type="button" aria-label="Analyse öffnen" :aria-pressed="mapStore.activeGisPanel === 'analytics'" @click="openAnalysis">
          <BarChart3 class="size-4" aria-hidden="true" /><span>Analyse</span>
        </button>
        <ClientOnly>
          <NuxtLink v-if="authStore.authenticated" class="map-action map-action-primary compact-create-action" to="/flaechen/neu" aria-label="Neue Fläche anlegen">
            <Plus class="size-4" aria-hidden="true" /><span>Neue Fläche</span>
          </NuxtLink>
        </ClientOnly>
      </nav>
    </section>

    <Transition name="gis-tool-panel">
      <GisToolPanel
        v-if="isCompact && mapStore.activeGisPanel !== null"
        :title="activePanelTitle"
        :close-label="activePanelCloseLabel"
        :content-key="activePanelContentKey"
        @close="closeGisPanel"
      >
        <GisPanelContent compact :result-label="resultLabel" @close="closeGisPanel" />
      </GisToolPanel>
    </Transition>

    <div class="hidden min-h-0 min-w-0 xl:block">
      <ClientOnly><LazyRightSidebar v-if="isDesktop" /></ClientOnly>
    </div>

    <AppBottomSheet
      :open="isMobile && mapStore.activeGisPanel !== null"
      :title="activePanelTitle"
      :close-label="activePanelCloseLabel"
      :content-key="activePanelContentKey"
      initial-snap="medium"
      @update:open="handleSheetOpen"
    >
      <GisPanelContent :result-label="resultLabel" @close="closeGisPanel" />
    </AppBottomSheet>
  </section>
</template>

<script setup lang="ts">
import { BarChart3, ListFilter, Plus, Search } from 'lucide-vue-next'

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
const isCompact = ref(false)
const isMobile = computed(() => !isDesktop.value && !isCompact.value)
const activeFilterCount = computed(() => filterStore.activeFilterCount + (osmStore.areaPoiFilter ? 1 : 0))
const resultCount = computed(() => usePolygonStore().polygons.length + (osmStore.areaPoiFilter ? osmStore.data?.meta.count || 0 : osmStore.data?.meta.business_count || 0))
const resultLabel = computed(() => resultCount.value ? `${resultCount.value} Ergebnisse anzeigen` : 'Keine Ergebnisse')
const activePanelTitle = computed(() => {
  if (mapStore.activeGisPanel === 'assistant') return 'Stadtplaner durchsuchen'
  if (mapStore.activeGisPanel === 'filter') return activeFilterCount.value ? `Filter · ${activeFilterCount.value} aktiv` : 'Filter'
  if (mapStore.activeGisPanel === 'selection' && mapStore.selectedMapEntity?.type === 'polygon') return 'Ausgewählte Fläche'
  if (osmStore.selectedFeature) return 'OpenStreetMap-Objekt'
  if (analysisAreasStore.selectedArea) return analysisAreasStore.selectedArea.name
  return 'Analyse'
})
const activePanelCloseLabel = computed(() => {
  if (mapStore.activeGisPanel === 'assistant') return 'Suche schließen'
  if (mapStore.activeGisPanel === 'filter') return 'Filter schließen'
  if (mapStore.activeGisPanel === 'selection') return 'Auswahl schließen'
  return 'Analyse schließen'
})
const activePanelContentKey = computed(() => {
  const entity = mapStore.selectedMapEntity
  if (mapStore.activeGisPanel !== 'selection' || !entity) return mapStore.activeGisPanel || 'closed'
  if (entity.type === 'polygon') return `polygon:${entity.id}`
  if (entity.type === 'osm') return `osm:${entity.feature.properties.osm_type}:${entity.feature.properties.osm_id}`
  return `analysis-area:${entity.id}`
})

let analyticsTimer: ReturnType<typeof setTimeout> | undefined
let desktopQuery: MediaQueryList | undefined
let compactQuery: MediaQueryList | undefined
let panelHistoryActive = false
let closingFromHistory = false

onMounted(() => {
  mapStore.closeGisPanels()
  desktopQuery = window.matchMedia('(min-width: 1280px)')
  compactQuery = window.matchMedia('(min-width: 900px) and (max-width: 1279px) and (min-height: 560px)')
  updateResponsiveMode()
  desktopQuery.addEventListener('change', handleResponsiveBreakpoint)
  compactQuery.addEventListener('change', handleResponsiveBreakpoint)
  window.addEventListener('popstate', handlePopState)
})

watch(() => mapStore.activeGisPanel, (panel, previous) => {
  if (!import.meta.client) return
  if (previous === 'assistant' && panel !== 'assistant' && searchStore.assistantOpen) searchStore.closeAssistant()
  if (panel && !previous) {
    window.history.pushState({ ...window.history.state, gisPanel: true }, '')
    panelHistoryActive = true
  } else if (!panel && previous && panelHistoryActive && !closingFromHistory) {
    panelHistoryActive = false
    const state = { ...window.history.state }
    delete state.gisPanel
    window.history.replaceState(state, '')
  }
})

watch(() => searchStore.assistantOpen, (open) => {
  if (!import.meta.client || isDesktop.value) return
  if (open) mapStore.openGisPanel('assistant')
  else if (mapStore.activeGisPanel === 'assistant') mapStore.closeGisPanel()
})

watch(() => filterStore.filterKey, () => {
  if (!analyticsIsVisible()) return
  clearTimeout(analyticsTimer)
  analyticsTimer = setTimeout(() => analyticsStore.load(), 180)
  if (analysisAreasStore.selectedAreaId) void analysisAreasStore.loadDetails()
})

watch(() => analysisAreasStore.selectedAreaId, () => {
  if (!analyticsIsVisible()) return
  clearTimeout(analyticsTimer)
  analyticsTimer = setTimeout(() => analyticsStore.load(), 80)
})

onBeforeUnmount(() => {
  clearTimeout(analyticsTimer)
  panelHistoryActive = false
  mapStore.closeGisPanels()
  mapSelection.clearSelection()
  searchStore.dispose()
  desktopQuery?.removeEventListener('change', handleResponsiveBreakpoint)
  compactQuery?.removeEventListener('change', handleResponsiveBreakpoint)
  window.removeEventListener('popstate', handlePopState)
})

function openFilter() { mapStore.openGisPanel('filter') }
function openAnalysis() { mapStore.openGisPanel('analytics'); void analyticsStore.load() }
function openSearch() { searchStore.openAssistant(); mapStore.openGisPanel('assistant') }
function handleSheetOpen(open: boolean) { if (!open) closeGisPanel() }

function closeGisPanel() {
  if (mapStore.activeGisPanel === 'selection') mapSelection.clearSelection()
  if (mapStore.activeGisPanel === 'assistant') searchStore.closeAssistant()
  mapStore.closeGisPanel()
}

function handleResponsiveBreakpoint() {
  const wasDesktop = isDesktop.value
  updateResponsiveMode()
  if (!wasDesktop && isDesktop.value) {
    void analyticsStore.load()
    mapStore.closeGisPanel()
  } else if (wasDesktop && !isDesktop.value && searchStore.assistantOpen) {
    mapStore.openGisPanel('assistant')
  }
}

function updateResponsiveMode() {
  isDesktop.value = Boolean(desktopQuery?.matches)
  isCompact.value = !isDesktop.value && Boolean(compactQuery?.matches)
  if (isDesktop.value) void analyticsStore.load()
}

function analyticsIsVisible() { return isDesktop.value || mapStore.activeGisPanel === 'analytics' }

function handlePopState() {
  if (!panelHistoryActive || !mapStore.activeGisPanel) return
  panelHistoryActive = false
  closingFromHistory = true
  if (mapStore.activeGisPanel === 'selection') mapSelection.clearSelection()
  if (mapStore.activeGisPanel === 'assistant') searchStore.closeAssistant()
  mapStore.closeGisPanel()
  nextTick(() => { closingFromHistory = false })
}
</script>

<style scoped>
.overview-shell { height: calc(100vh - var(--app-header-height)); }
.map-action { display: inline-flex; height: 2.75rem; min-width: 2.75rem; align-items: center; justify-content: center; gap: 0.375rem; border: 1px solid transparent; border-radius: 0.75rem; padding-inline: 0.65rem; color: #334155; font-size: 0.75rem; font-weight: 800; cursor: pointer; transition: background-color 150ms, border-color 150ms, color 150ms, box-shadow 150ms; white-space: nowrap; }
.map-action:hover { background: #f1f5f9; }
.map-action-active { border-color: #8baabd; background: #e2edf4; color: #154d73; }
.map-action:focus-visible { outline: 2px solid #154d73; outline-offset: 2px; }
.map-action-primary { border-color: #154d73; background: #154d73; color: white; }
.map-action-primary:hover { background: #0f3f61; }
.mobile-map-actions { bottom: calc(env(safe-area-inset-bottom) + 2.25rem); display: grid; width: min(calc(100% - 1rem), 25rem); max-width: calc(100% - 1rem); grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.375rem; }
.mobile-map-actions .map-action-primary { grid-column: 1 / -1; grid-row: 1; }

@media (min-width: 480px) {
  .mobile-map-actions { width: auto; grid-template-columns: repeat(4, max-content); }
  .mobile-map-actions .map-action-primary { grid-column: auto; grid-row: auto; }
}
@supports (height: 100dvh) { .overview-shell { height: calc(100dvh - var(--app-header-height)); } }

@media (min-width: 900px) and (max-width: 1279px) and (min-height: 560px) {
  .overview-shell { display: grid; gap: 0.75rem; padding: 0.75rem; grid-template-columns: minmax(0, 1fr); transition: grid-template-columns 220ms ease-out; }
  .overview-shell[data-compact-panel-open='true'] { grid-template-columns: minmax(0, 1fr) clamp(340px, 34vw, 420px); }
  .gis-map-stage { position: relative; inset: auto; padding: 0; }
  .mobile-map-actions { bottom: 1.25rem; }
}
@media (min-width: 1024px) and (max-width: 1279px) { .compact-create-action { display: none; } }
@media (min-width: 1280px) {
  .mobile-map-actions { display: none; }
  .overview-shell { display: grid; min-height: 620px; grid-template-columns: 272px minmax(0, 1fr) 312px; gap: 1rem; padding: 1rem; }
  .overview-shell[data-assistant-open='true'] { grid-template-columns: minmax(380px, 400px) minmax(0, 1fr) 312px; }
}
@media (min-width: 1440px) {
  .overview-shell { grid-template-columns: 288px minmax(600px, 1fr) 328px; }
  .overview-shell[data-assistant-open='true'] { grid-template-columns: 420px minmax(600px, 1fr) 328px; }
}
.gis-tool-panel-enter-active, .gis-tool-panel-leave-active { transition: opacity 180ms ease-out, transform 220ms ease-out; }
.gis-tool-panel-enter-from, .gis-tool-panel-leave-to { opacity: 0; transform: translateX(1rem); }
@media (prefers-reduced-motion: reduce) { .overview-shell, .gis-tool-panel-enter-active, .gis-tool-panel-leave-active { transition: none; } }
</style>
