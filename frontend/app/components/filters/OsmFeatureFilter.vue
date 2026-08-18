<template>
  <section aria-labelledby="osm-filter-title">
    <h3 id="osm-filter-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">OpenStreetMap</h3>
    <div class="mt-3 grid gap-1 text-sm text-slate-700" :class="{ 'opacity-60': !osmEnabled }">
      <GisFilterToggleRow v-model="osm.showPois" label="POIs anzeigen" aria-label="OpenStreetMap-POIs anzeigen" :disabled="!osmEnabled" />
      <GisFilterToggleRow v-model="osm.showAreas" label="Flächenobjekte anzeigen" aria-label="OpenStreetMap-Flächenobjekte anzeigen" :disabled="!osmEnabled" />
      <GisFilterToggleRow v-model="osm.showBuildings" label="Gebäude ab Zoom 17" aria-label="OpenStreetMap-Gebäude anzeigen" :disabled="!osmEnabled" />
    </div>
    <details class="mt-2" :class="{ 'pointer-events-none opacity-50': !osmEnabled || !osm.showPois }" :aria-disabled="!osmEnabled || !osm.showPois">
      <summary class="flex min-h-11 cursor-pointer items-center text-sm font-bold text-[#154d73]">POI-Kategorien auswählen</summary>
      <div class="grid gap-1 pb-1">
        <label v-for="category in osmPoiCategories" :key="category.key" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-2 hover:bg-slate-50">
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

const osm = useOsmViewportStore()
const filter = useFilterStore()
const osmEnabled = computed(() => filter.selectedSources.includes('OSM'))
</script>
