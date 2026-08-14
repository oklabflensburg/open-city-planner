<template>
  <Card class="p-4" :data-render-ms="osm.lastRenderDurationMs">
    <div class="flex items-start justify-between gap-3">
      <div><h2 class="text-sm font-bold text-slate-800">Aktueller Kartenausschnitt</h2><p class="mt-1 text-[11px] text-slate-500">Lokale OpenStreetMap-Daten</p></div>
      <LoaderCircle v-if="osm.loading" class="size-4 animate-spin text-[#154d73]" aria-label="OSM-Daten werden geladen" />
    </div>
    <p v-if="osm.error" class="mt-3 rounded-lg bg-rose-50 p-2 text-xs text-rose-800">{{ osm.error }}</p>
    <p v-else-if="!osm.data?.meta.count" class="mt-3 text-xs leading-5 text-slate-500">In dieser Ansicht sind keine aktivierten OSM-Objekte sichtbar.</p>
    <dl v-else class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
      <template v-for="item in summary" :key="item.key">
        <dt class="truncate text-slate-600">{{ item.label }}</dt><dd class="text-right font-bold tabular-nums text-slate-900">{{ item.count }}</dd>
      </template>
    </dl>
    <p v-if="osm.data?.meta.truncated" class="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">Nicht alle Objekte passen in die Ansicht. Zoomen Sie weiter hinein.</p>
    <p v-if="osm.data?.meta.osm_data_updated_at" class="mt-3 text-[10px] text-slate-500">OSM-Datenstand: {{ formatDate(osm.data.meta.osm_data_updated_at) }}</p>
  </Card>
</template>

<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next'
import { osmCategoryLabels } from '~/utils/osmCategories'

const osm = useOsmViewportStore()
const summary = computed(() => Object.entries(osm.data?.meta.summary || {})
  .map(([key, count]) => ({ key, label: osmCategoryLabels[key as keyof typeof osmCategoryLabels] || key, count }))
  .sort((a, b) => b.count - a.count))
const formatDate = (value: string) => new Intl.DateTimeFormat('de-DE').format(new Date(value))
</script>
