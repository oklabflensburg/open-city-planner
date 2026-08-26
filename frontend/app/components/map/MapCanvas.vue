<template>
  <div class="relative h-full min-h-0 min-w-0 overflow-hidden rounded-[var(--radius-panel)] border border-white bg-[var(--c-surface-muted)] shadow-[var(--shadow-card)] lg:min-h-[420px]">
    <span v-if="socialPreview" class="sr-only" :data-social-preview-ready="gisPreviewReady ? 'true' : 'false'">Kartenvorschau bereit</span>
    <span class="sr-only" :data-search-layer-count="mapStore.searchAction?.data?.features.length || 0">Suchergebnisse auf der Karte</span>
    <div ref="mapEl" class="absolute inset-0 h-full w-full" role="region" aria-label="Interaktive Stadtkarte von Flensburg" />
    <div v-if="!mapStore.mapLoaded && !mapError" class="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-slate-100/90" role="status" aria-live="polite">
      <div class="flex items-center gap-3 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">
        <LoaderCircle class="size-5 animate-spin text-[#154d73]" aria-hidden="true" />
        Karte wird geladen …
      </div>
    </div>
    <div class="pointer-events-none absolute right-3 top-3 z-10">
      <MapControlsContainer
        @zoom-in="map?.zoomIn()"
        @zoom-out="map?.zoomOut()"
        @reset="resetView"
      />
      <UiContributionSlot class="pointer-events-auto mt-2" slot="map.controls" />
    </div>
    <UiContributionSlot class="pointer-events-auto absolute inset-x-3 bottom-3 z-10 xl:hidden" slot="map.bottomSheet" />
    <UiContributionSlot class="pointer-events-auto absolute left-3 top-3 z-10" slot="map.contextMenu" />
    <div v-if="mapError" class="absolute inset-x-3 top-1/2 z-30 mx-auto max-w-sm -translate-y-1/2 rounded-xl border border-rose-200 bg-white p-4 text-center shadow-xl" role="alert">
      <p class="text-sm font-bold text-rose-800">Karte konnte nicht geladen werden.</p>
      <p class="mt-1 break-words text-xs leading-5 text-slate-600">{{ mapError }}</p>
      <button class="mt-3 inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl bg-[#154d73] px-4 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="retryMap">
        <RefreshCw class="size-4" aria-hidden="true" /> Erneut versuchen
      </button>
    </div>
    <div v-else-if="polygonStore.error" class="absolute bottom-24 left-3 z-10 max-w-[calc(100%-1.5rem)] rounded-lg bg-white px-3 py-2 text-xs text-red-700 shadow lg:bottom-16 lg:max-w-[320px]">
      {{ polygonStore.error }}
    </div>
    <div v-else-if="showEmptyState" class="absolute bottom-3 left-3 z-10 flex max-w-[calc(100%-1.5rem)] items-center gap-3 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow lg:bottom-4 lg:max-w-[360px]" role="status" aria-live="polite">
      <span class="font-semibold">0 Treffer für die aktuelle Auswahl</span>
      <button class="min-h-8 shrink-0 cursor-pointer rounded-md px-2 font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="resetVisibleFilters">Filter aufheben</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LoaderCircle, RefreshCw } from '@lucide/vue'

const {
  mapEl,
  map,
  mapError,
  socialPreview,
  gisPreviewReady,
  mapStore,
  polygonStore,
  showEmptyState,
  resetView,
  resetVisibleFilters,
  retryMap
} = useMapCanvasHost()
</script>

<style scoped>
:deep(.maplibregl-ctrl-attrib a) {
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>
