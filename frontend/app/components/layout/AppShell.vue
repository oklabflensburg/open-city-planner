<template>
  <section class="overview-shell relative min-h-0 min-w-0 overflow-hidden bg-[#f4f4f4] text-[#2f3337] lg:grid lg:gap-3 lg:p-3">
    <div class="hidden min-h-0 min-w-0 lg:block">
      <ClientOnly>
        <LazyLeftSidebar v-if="isDesktop" />
      </ClientOnly>
    </div>

    <section class="absolute inset-0 min-h-0 min-w-0 p-2 lg:relative lg:inset-auto lg:p-0" aria-label="Stadtplaner-Karte">
      <LazyMapCanvas hydrate-on-idle />

      <nav
        v-if="mapStore.activeMobilePanel === null"
        class="absolute bottom-[calc(env(safe-area-inset-bottom)+2.25rem)] left-1/2 z-20 grid max-w-[calc(100%-1rem)] -translate-x-1/2 grid-flow-col auto-cols-max gap-1.5 rounded-2xl border border-slate-200 bg-white/95 p-1.5 shadow-xl backdrop-blur lg:hidden"
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
        <NuxtLink v-if="authStore.authenticated" class="map-action map-action-primary" to="/flaechen/neu" aria-label="Neue Fläche anlegen">
          <Plus class="size-4" aria-hidden="true" />
          <span>Neue Fläche</span>
        </NuxtLink>
      </nav>
    </section>

    <div class="hidden min-h-0 min-w-0 lg:block">
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
        <LazyLeftSidebar />
        <div class="mt-3 grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <button class="min-h-11 rounded-xl border border-slate-300 px-3 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="resetFilters">Zurücksetzen</button>
          <button class="min-h-11 rounded-xl bg-[#154d73] px-3 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="closeMobilePanel">Fertig</button>
        </div>
      </template>
      <LazyRightSidebar v-else-if="mapStore.activeMobilePanel === 'analytics'" />
      <div v-else-if="mapStore.activeMobilePanel === 'selection'" class="-m-3 min-h-full bg-white p-4">
        <MapSelectionContent embedded />
      </div>
    </AppBottomSheet>
  </section>
</template>

<script setup lang="ts">
import { BarChart3, ListFilter, Plus } from 'lucide-vue-next'

const mapStore = useMapStore()
const filterStore = useFilterStore()
const analyticsStore = useAnalyticsStore()
const osmStore = useOsmViewportStore()
const analysisAreasStore = useAnalysisAreasStore()
const authStore = useAuthStore()
const mapSelection = useMapSelection()
const isDesktop = ref(false)
const activeFilterCount = computed(() => (
  (filterStore.selectedSize !== 'M' ? 1 : 0)
  + (filterStore.selectedFloor !== 'EG' ? 1 : 0)
  + (filterStore.allCategoriesActive ? 0 : 1)
  + (filterStore.occupancyStatuses.length ? 1 : 0)
  + (filterStore.businessStructures.length ? 1 : 0)
  + (!osmStore.showPois || !osmStore.showAreas || osmStore.showBuildings ? 1 : 0)
  + (osmStore.activeCategories.length === 15 ? 0 : 1)
))
const activePanelTitle = computed(() => {
  if (mapStore.activeMobilePanel === 'filter') return 'Filter & Ansichten'
  if (mapStore.activeMobilePanel === 'selection' && mapStore.selectedMapEntity?.type === 'polygon') return 'Ausgewählte Fläche'
  if (osmStore.selectedFeature) return 'OpenStreetMap-Objekt'
  if (analysisAreasStore.selectedArea) return analysisAreasStore.selectedArea.name
  return 'Kennzahlen & Analyse'
})
const activePanelCloseLabel = computed(() => {
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
  desktopQuery = window.matchMedia('(min-width: 1024px)')
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
    window.history.back()
  }
})

watch(
  () => [filterStore.selectedSize, filterStore.selectedFloor, ...filterStore.activeCategories, ...filterStore.occupancyStatuses, ...filterStore.businessStructures],
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
  if (panelHistoryActive && window.history.state?.mobileGisPanel) {
    panelHistoryActive = false
    window.history.back()
  }
  mapStore.closeMobilePanels()
  mapSelection.clearSelection()
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

function handleSheetOpen(open: boolean) {
  if (!open) closeMobilePanel()
}

function closeMobilePanel() {
  if (mapStore.activeMobilePanel === 'selection') mapSelection.clearSelection()
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

@media (min-width: 1024px) {
  .overview-shell {
    min-height: 620px;
    grid-template-columns: 260px minmax(0, 1fr) 300px;
  }
}

@media (min-width: 1440px) {
  .overview-shell { grid-template-columns: 280px minmax(600px, 1fr) 320px; }
}
</style>
