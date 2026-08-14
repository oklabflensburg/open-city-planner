<template>
  <section aria-labelledby="osm-filter-title">
    <h3 id="osm-filter-title" class="text-xs font-bold uppercase tracking-wide text-slate-500">OpenStreetMap</h3>
    <div class="mt-3 grid gap-2 text-sm text-slate-700">
      <label class="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3">
        <input v-model="osm.showPois" class="size-4 accent-[#154d73]" type="checkbox"> POIs anzeigen
      </label>
      <label class="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3">
        <input v-model="osm.showAreas" class="size-4 accent-[#154d73]" type="checkbox"> Flächenobjekte anzeigen
      </label>
      <label class="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3">
        <input v-model="osm.showBuildings" class="size-4 accent-[#154d73]" type="checkbox"> Gebäude ab Zoom 17
      </label>
    </div>
    <details class="mt-2" :class="{ 'opacity-50': !osm.showPois }">
      <summary class="flex min-h-11 cursor-pointer items-center text-sm font-bold text-[#154d73]">POI-Kategorien auswählen</summary>
      <div class="grid gap-1 pb-1">
        <label v-for="category in osmPoiCategories" :key="category.key" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-2 hover:bg-slate-50">
          <input :checked="osm.activeCategories.includes(category.key)" :disabled="!osm.showPois" class="size-4 accent-[#154d73]" type="checkbox" @change="osm.toggleCategory(category.key)">
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
</script>
