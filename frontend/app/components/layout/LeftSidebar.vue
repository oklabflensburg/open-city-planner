<template>
  <aside class="min-w-0 rounded-2xl border border-slate-200/80 bg-white shadow-sm lg:h-full lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain">
    <section>
      <header class="flex items-center gap-2 border-b border-slate-100 px-4 py-4">
        <ListFilter class="size-4 text-[#154d73]" aria-hidden="true" />
        <h2 class="text-sm font-bold text-slate-800">Filter &amp; Ansichten</h2>
      </header>
      <div class="divide-y divide-slate-200 px-4">
        <div class="space-y-6 py-5">
          <AreaFilter />
          <FloorFilter />
          <IndustryFilter />
          <MarketStatusFilter />
        </div>
        <section class="py-5" aria-labelledby="map-display-title">
          <h3 id="map-display-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">Kartendarstellung</h3>
          <div class="mt-3 grid gap-1">
            <label v-for="theme in mapThemes" :key="theme.key" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm text-slate-700 hover:bg-slate-50">
              <input v-model="mapStore.thematicStyle" class="accent-[#154d73]" type="radio" name="sidebar-map-theme" :value="theme.key">
              {{ theme.label }}
            </label>
          </div>
        </section>
        <section class="py-5" aria-labelledby="map-layers-title">
          <h3 id="map-layers-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">Layer</h3>
          <label class="mt-3 flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 text-sm text-slate-700">
            <input v-model="mapStore.polygonsVisible" class="size-4 accent-[#154d73]" type="checkbox"> Verkaufsflächen anzeigen
          </label>
          <div class="mt-3 rounded-xl border border-slate-200 p-2" aria-label="Administrative Gebietsgrenzen">
            <p class="px-1 pb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Gebietsgrenzen</p>
            <label v-for="item in areaLayers" :key="item.type" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-1 text-sm text-slate-700 hover:bg-slate-50">
              <input v-model="analysisAreasStore.visibility[item.type]" class="size-4 accent-[#154d73]" type="checkbox">
              <span class="size-3 rounded-sm border" :style="{ backgroundColor: item.color, borderColor: item.border }" aria-hidden="true" />
              {{ item.label }}
            </label>
          </div>
          <OsmFeatureFilter class="mt-5" />
        </section>
        <MapLegend class="py-5" :theme="mapStore.thematicStyle" />
        <section class="py-5" aria-labelledby="filter-hint-title">
          <div class="flex items-center gap-2 text-[#154d73]">
            <Info class="size-4" aria-hidden="true" />
            <h2 id="filter-hint-title" class="text-sm font-bold">Hinweis</h2>
          </div>
          <p class="mt-2 text-xs leading-5 text-slate-600">Wählen Sie eine Verkaufsfläche, ein OpenStreetMap-Objekt oder ein Gebiet aus, um rechts Details anzusehen.</p>
        </section>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { Info, ListFilter } from 'lucide-vue-next'
import { mapThemes } from '~/utils/mapThemes'

const mapStore = useMapStore()
const analysisAreasStore = useAnalysisAreasStore()
const areaLayers = [
  { type: 'MUNICIPALITY' as const, label: 'Gemeinde', color: '#dbeafe', border: '#1d4ed8' },
  { type: 'DISTRICT' as const, label: 'Stadtteile', color: '#dcfce7', border: '#15803d' },
  { type: 'QUARTER' as const, label: 'Quartiere', color: '#fef3c7', border: '#b45309' }
]
</script>
