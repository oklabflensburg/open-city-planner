<template>
  <section aria-labelledby="osm-filter-title">
    <h3 id="osm-filter-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">OpenStreetMap</h3>
    <div v-if="osm.poi" class="mt-3 flex items-center justify-between gap-3 rounded-xl border border-[#8baabd] bg-[#edf5f8] p-3">
      <p class="min-w-0 text-xs font-semibold text-[#154d73]">POI-Kategorie: {{ getPoiCategoryLabel(osm.poi) }}</p>
      <button class="min-h-8 shrink-0 cursor-pointer rounded-lg px-2 text-xs font-bold text-[#154d73] hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" type="button" @click="osm.clearPoi()">Entfernen</button>
    </div>
    <div class="mt-3 grid gap-1 text-sm text-slate-700" :class="{ 'opacity-60': !osmEnabled }">
      <GisFilterToggleRow v-model="osm.showPois" label="Orte und Einrichtungen anzeigen" aria-label="Orte und Einrichtungen aus OpenStreetMap anzeigen" :disabled="!osmEnabled" />
      <GisFilterToggleRow v-model="osm.showAreas" label="Flächenobjekte anzeigen" aria-label="OpenStreetMap-Flächenobjekte anzeigen" :disabled="!osmEnabled" />
      <GisFilterToggleRow v-model="osm.showBuildings" label="Gebäude ab Zoom 17" aria-label="OpenStreetMap-Gebäude anzeigen" :disabled="!osmEnabled" />
    </div>
    <details class="mt-2" :class="{ 'pointer-events-none opacity-50': !osmEnabled || !osm.showPois }" :aria-disabled="!osmEnabled || !osm.showPois">
      <summary class="flex min-h-11 cursor-pointer items-center text-sm font-bold text-[#154d73]">Kategorien für Orte auswählen</summary>
      <div class="grid gap-1 pb-1">
        <label
          v-for="category in osmPoiCategories"
          :key="category.key"
          class="flex min-h-10 items-center gap-2 rounded-lg px-2 hover:bg-slate-50"
          :class="!osmEnabled || !osm.showPois ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
        >
          <input :checked="osm.activeCategories.includes(category.key)" :disabled="!osmEnabled || !osm.showPois" class="size-4 accent-[#154d73]" type="checkbox" @change="osm.toggleCategory(category.key)">
          <span class="size-2.5 rounded-full" :style="{ backgroundColor: category.color }" aria-hidden="true" />
          <span>{{ category.label }}</span>
        </label>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { osmPoiCategories } from '~/utils/osmCategories'
import { getPoiCategoryLabel } from '~/utils/poiCategories'

const osm = useOsmViewportStore()
const filter = useFilterStore()
const osmEnabled = computed(() => filter.selectedSources.includes('OSM'))
</script>
