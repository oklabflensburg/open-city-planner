<template>
  <aside
    class="max-w-full min-w-0"
    :class="embedded ? 'bg-transparent' : 'flex h-full min-h-0 flex-col gap-3 overflow-hidden'"
  >
    <section :class="embedded ? '' : 'civic-card min-h-0 flex-1 overflow-y-auto overscroll-contain'">
      <header
        data-filter-summary
        :class="embedded
          ? compact ? 'border-b border-slate-200 px-1 pb-3' : 'border-b border-slate-200 px-4 pb-3'
          : 'sticky top-0 z-10 border-b border-slate-100 bg-white px-4 py-3'"
      >
        <div v-if="!embedded" class="flex items-center gap-2">
          <ListFilter class="size-4 text-[#154d73]" aria-hidden="true" />
          <h2 class="text-sm font-bold text-slate-800">Filter</h2>
          <span v-if="activeFilterCount" class="rounded-full bg-[#e2edf4] px-2 py-0.5 text-[11px] font-black text-[#154d73]">{{ activeFilterCount }} aktiv</span>
          <button v-if="canReset" class="ml-auto min-h-8 cursor-pointer rounded-md px-2 text-xs font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="resetAll">Zurücksetzen</button>
        </div>
        <template v-if="compact">
          <div class="flex min-w-0 items-start gap-2">
            <p class="min-w-0 flex-1 text-xs font-semibold leading-5 text-slate-700">{{ compactFilterStatus }}</p>
            <button v-if="canReset" class="min-h-8 shrink-0 cursor-pointer rounded-md px-2 text-xs font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="resetAll">Zurücksetzen</button>
          </div>
          <p class="mt-0.5 text-xs font-bold text-slate-600">{{ compactResultSummary }}</p>
          <details class="mt-1 text-[11px] leading-4 text-slate-500">
            <summary class="min-h-8 cursor-pointer py-1.5 font-semibold text-[#154d73]">Wie wirken Filter?</summary>
            <p class="pb-1">Filter gelten für Stadtplaner-Flächen und passende lokale OpenStreetMap-Objekte. Fehlende Angaben bleiben nur in der vollständigen Auswahl enthalten.</p>
          </details>
        </template>
        <template v-else>
        <p :class="embedded ? '' : 'mt-2'" class="text-[11px] font-semibold leading-4 text-slate-600">{{ filterStatus }}</p>
        <p v-if="!filter.selectedSources.length" class="mt-1 text-[11px] font-semibold leading-4 text-amber-700">Keine Fachdatenquelle ausgewählt. Die Basiskarte bleibt sichtbar.</p>
        <p class="mt-1 text-[11px] leading-4 text-slate-500">Gilt für Stadtplaner-Flächen und passende lokale OpenStreetMap-Objekte. Fehlende Angaben sind in der vollständigen Auswahl enthalten und werden bei Teilfiltern nicht geschätzt.</p>
        <p class="mt-1 text-[11px] font-semibold text-slate-600">{{ resultSummary }}</p>
        </template>
      </header>
      <div class="min-w-0 divide-y divide-slate-200 px-4">
        <div class="space-y-6 py-5">
          <AreaFilter />
          <FloorFilter />
          <IndustryFilter />
          <MarketStatusFilter />
          <DataSourceFilter />
        </div>
        <section class="py-5" aria-labelledby="map-display-title">
          <h3 id="map-display-title" class="text-xs font-bold uppercase tracking-wide text-slate-600">Kartendarstellung</h3>
          <div class="mt-3 grid gap-1">
            <label v-for="theme in mapThemes" :key="theme.key" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm text-slate-700 hover:bg-slate-50">
              <input v-model="mapStore.thematicStyle" class="accent-[#154d73]" type="radio" name="sidebar-map-theme" :value="theme.key">
              {{ theme.label }}
            </label>
          </div>
        </section>
        <section class="py-5" aria-labelledby="map-layers-title">
          <h3 id="map-layers-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">Layer</h3>
          <GisFilterToggleRow
            v-model="mapStore.polygonsVisible"
            class="mt-3"
            label="Verkaufsflächen anzeigen"
            aria-label="Verkaufsflächen anzeigen"
          />
          <UiContributionSlot class="mt-4" slot="map.layers" />
          <OsmFeatureFilter class="mt-5" />
        </section>
        <MapLegend class="py-5" :theme="mapStore.thematicStyle" />
        <section class="py-5" aria-labelledby="filter-hint-title">
          <div class="flex items-center gap-2 text-[#154d73]">
            <Info class="size-4" aria-hidden="true" />
            <h2 id="filter-hint-title" class="text-sm font-bold">Hinweis</h2>
          </div>
          <p class="mt-2 text-xs leading-5 text-slate-600">Wählen Sie eine Verkaufsfläche, ein OpenStreetMap-Objekt oder einen Modul-Layer aus, um rechts Details anzusehen.</p>
        </section>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { Info, ListFilter } from '@lucide/vue'
import { mapThemes } from '~/utils/mapThemes'
import { getPoiCategoryLabel } from '~/utils/poiCategories'

withDefaults(defineProps<{ embedded?: boolean, compact?: boolean }>(), { embedded: false, compact: false })

const mapStore = useMapStore()
const filter = useFilterStore()
const polygonStore = usePolygonStore()
const osmStore = useOsmViewportStore()
const activeFilterCount = computed(() => filter.activeFilterCount + (osmStore.poi ? 1 : 0))
const canReset = computed(() => filter.canReset || Boolean(osmStore.poi))
const filterStatus = computed(() => {
  const descriptions = [...filter.activeFilterDescriptions]
  if (osmStore.poi) descriptions.push(`POI: ${getPoiCategoryLabel(osmStore.poi)}`)
  return descriptions.length
    ? `${descriptions.length} Filter aktiv · ${descriptions.join(' · ')}`
    : 'Alle passenden Objekte werden angezeigt.'
})
const resultSummary = computed(() => {
  const polygonCount = polygonStore.polygons.length
  const osmCount = osmStore.data?.meta.business_count || 0
  return `${polygonCount} Stadtplaner · ${osmCount} OSM im Ausschnitt`
})
const compactFilterStatus = computed(() => {
  const descriptions = [...filter.activeFilterDescriptions]
  if (osmStore.poi) descriptions.push(`POI: ${getPoiCategoryLabel(osmStore.poi)}`)
  return descriptions.length ? descriptions.join(' · ') : 'Alle passenden Objekte'
})
const compactResultSummary = computed(() => {
  const polygonCount = polygonStore.polygons.length
  const osmCount = osmStore.data?.meta.business_count || 0
  return `${polygonCount} Flächen · ${osmCount} OSM`
})
function resetAll() {
  filter.reset()
  osmStore.reset()
}
</script>
