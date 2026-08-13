<template>
  <section class="overview-shell relative min-h-0 min-w-0 overflow-hidden bg-[#f4f4f4] text-[#2f3337] lg:grid lg:gap-3 lg:p-3">
    <div class="hidden min-h-0 min-w-0 lg:block">
      <LeftSidebar />
    </div>

    <section class="absolute inset-0 min-h-0 min-w-0 p-2 lg:relative lg:inset-auto lg:p-0" aria-label="Stadtplaner-Karte">
      <MapCanvas />

      <NuxtLink
        v-if="authStore.authenticated"
        class="absolute left-16 top-3 z-20 hidden min-h-11 items-center gap-2 rounded-xl border border-[#154d73] bg-[#154d73] px-4 text-sm font-bold text-white shadow-lg transition hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] lg:inline-flex"
        to="/flaechen/neu"
        aria-label="Neue Fläche anlegen"
      >
        <Plus class="size-4" aria-hidden="true" />
        Neue Fläche
      </NuxtLink>

      <nav
        v-if="!mapStore.polygonPreviewOpen"
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
      <RightSidebar />
    </div>

    <AppBottomSheet
      :open="mapStore.activeMobilePanel !== null"
      :title="activePanelTitle"
      :close-label="activePanelCloseLabel"
      :content-key="mapStore.activeMobilePanel || 'closed'"
      initial-snap="medium"
      @update:open="handleSheetOpen"
    >
      <template v-if="mapStore.activeMobilePanel === 'filter'">
        <LeftSidebar />
        <div class="mt-3 grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <button class="min-h-11 rounded-xl border border-slate-300 px-3 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="filterStore.reset">Zurücksetzen</button>
          <button class="min-h-11 rounded-xl bg-[#154d73] px-3 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="closeMobilePanel">Fertig</button>
        </div>
      </template>
      <RightSidebar v-else-if="mapStore.activeMobilePanel === 'analytics'" />
    </AppBottomSheet>

    <Drawer :open="mapStore.polygonPreviewOpen" side="bottom" label="Ausgewählte Fläche" @close="closePreview">
      <div class="min-w-0 bg-[#f4f4f4] p-3 pt-2">
        <div class="mx-auto mb-2 h-1 w-10 rounded-full bg-slate-300" aria-hidden="true" />
        <div class="max-h-[calc(min(72dvh,620px)-env(safe-area-inset-bottom))] min-w-0 overflow-y-auto overscroll-contain">
          <PolygonStatistics />
        </div>
      </div>
    </Drawer>
  </section>
</template>

<script setup lang="ts">
import { BarChart3, ListFilter, Plus } from 'lucide-vue-next'

const mapStore = useMapStore()
const filterStore = useFilterStore()
const analyticsStore = useAnalyticsStore()
const authStore = useAuthStore()
const activeFilterCount = computed(() => (
  (filterStore.selectedSize !== 'M' ? 1 : 0)
  + (filterStore.selectedFloor !== 'EG' ? 1 : 0)
  + (filterStore.allCategoriesActive ? 0 : 1)
))
const activePanelTitle = computed(() => mapStore.activeMobilePanel === 'filter' ? 'Filter & Ansichten' : 'Kennzahlen & Analyse')
const activePanelCloseLabel = computed(() => mapStore.activeMobilePanel === 'filter' ? 'Filter schließen' : 'Analyse schließen')

let analyticsTimer: ReturnType<typeof setTimeout> | undefined
let desktopQuery: MediaQueryList | undefined
let panelHistoryActive = false
let closingFromHistory = false

onMounted(() => {
  mapStore.closeMobilePanels()
  void analyticsStore.load()
  desktopQuery = window.matchMedia('(min-width: 1024px)')
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
  () => [filterStore.selectedSize, filterStore.selectedFloor, ...filterStore.activeCategories],
  () => {
    clearTimeout(analyticsTimer)
    analyticsTimer = setTimeout(() => analyticsStore.load(), 180)
  }
)

onBeforeUnmount(() => {
  clearTimeout(analyticsTimer)
  if (panelHistoryActive && window.history.state?.mobileGisPanel) {
    panelHistoryActive = false
    window.history.back()
  }
  mapStore.closeMobilePanels()
  desktopQuery?.removeEventListener('change', handleDesktopBreakpoint)
  window.removeEventListener('popstate', handlePopState)
})

function openFilter() {
  mapStore.openMobilePanel('filter')
}

function openAnalysis() {
  mapStore.openMobilePanel('analytics')
}

function handleSheetOpen(open: boolean) {
  if (!open) closeMobilePanel()
}

function closeMobilePanel() {
  mapStore.closeMobilePanel()
}

function closePreview() {
  mapStore.polygonPreviewOpen = false
}

function handleDesktopBreakpoint(event: MediaQueryListEvent) {
  if (event.matches) mapStore.closeMobilePanel()
}

function handlePopState() {
  if (!panelHistoryActive || !mapStore.activeMobilePanel) return
  panelHistoryActive = false
  closingFromHistory = true
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
  min-height: 2.75rem;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  border-radius: 0.75rem;
  padding-inline: 0.65rem;
  color: #334155;
  font-size: 0.75rem;
  font-weight: 800;
  white-space: nowrap;
}

.map-action:hover { background: #f1f5f9; }
.map-action-active { background: #e2edf4; color: #154d73; }
.map-action:focus-visible { outline: 2px solid #154d73; outline-offset: 2px; }
.map-action-primary { background: #154d73; color: white; }
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
