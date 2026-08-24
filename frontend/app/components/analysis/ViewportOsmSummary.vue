<template>
  <Card class="p-4" :data-render-ms="osm.lastRenderDurationMs">
    <div class="flex items-start justify-between gap-3">
      <div><h2 class="text-sm font-bold text-slate-800">OpenStreetMap</h2><p class="mt-1 text-[11px] text-slate-500">Lokale, deduplizierte Daten im Kartenausschnitt</p></div>
      <LoaderCircle v-if="osm.loading" class="size-4 animate-spin text-[#154d73]" aria-label="OSM-Daten werden geladen" />
    </div>
    <p v-if="osm.error" class="mt-3 rounded-lg bg-rose-50 p-2 text-xs text-rose-800">{{ osm.error }}</p>
    <p v-else-if="!osm.data?.meta.count" class="mt-3 text-xs leading-5 text-slate-500">In dieser Ansicht sind keine aktivierten OSM-Objekte sichtbar.</p>
    <template v-else>
      <section aria-labelledby="osm-business-title" class="mt-3 rounded-xl bg-slate-50 p-3">
        <div class="flex items-center justify-between gap-3"><h3 id="osm-business-title" class="text-xs font-bold text-slate-700">Gefilterte Flächen &amp; Standorte</h3><strong class="tabular-nums text-slate-900">{{ osm.data.meta.business_count }}</strong></div>
        <dl v-if="businessSummary.length" class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <template v-for="item in businessSummary" :key="item.key"><dt class="truncate text-slate-600">{{ item.label }}</dt><dd class="text-right font-bold tabular-nums">{{ item.count }}</dd></template>
        </dl>
        <p v-else class="mt-2 text-xs text-slate-500">Keine passenden Geschäftsobjekte.</p>
      </section>
      <h3 class="mt-4 text-xs font-bold uppercase tracking-wide text-slate-500">Umfeld im Kartenausschnitt</h3>
    <dl class="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
      <template v-for="item in visibleSummary" :key="item.key">
        <dt class="truncate text-slate-600">{{ item.label }}</dt><dd class="text-right font-bold tabular-nums text-slate-900">{{ item.count }}</dd>
      </template>
    </dl>
    </template>
    <button v-if="summary.length > 8" class="mt-3 min-h-9 cursor-pointer text-xs font-bold text-[#154d73] hover:underline" type="button" @click="expanded = !expanded">{{ expanded ? 'Weniger anzeigen' : `Alle ${summary.length} Kategorien anzeigen` }}</button>
    <p v-if="osm.data?.meta.truncated" class="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">Nicht alle Objekte passen in die Ansicht. Zoomen Sie weiter hinein.</p>
    <p v-if="osm.data?.meta.osm_data_updated_at" class="mt-3 text-[10px] text-slate-500">OSM-Datenstand: {{ formatDate(osm.data.meta.osm_data_updated_at) }}</p>
  </Card>
</template>

<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'
import { osmCategoryLabels } from '~/utils/osmCategories'
import { getIndustryLabel } from '~/utils/industries'

const osm = useOsmViewportStore()
const expanded = ref(false)
const businessSummary = computed(() => Object.entries(osm.data?.meta.canonical_summary || {})
  .map(([key, count]) => ({ key, label: getIndustryLabel(key), count }))
  .sort((a, b) => b.count - a.count))
const businessEnvironmentKeys = new Set(['retail', 'groceries', 'gastronomy', 'services'])
const summary = computed(() => Object.entries(osm.data?.meta.summary || {})
  .filter(([key]) => !businessEnvironmentKeys.has(key))
  .map(([key, count]) => ({ key, label: osmCategoryLabels[key as keyof typeof osmCategoryLabels] || key, count }))
  .sort((a, b) => b.count - a.count))
const visibleSummary = computed(() => expanded.value ? summary.value : summary.value.slice(0, 8))
const formatDate = (value: string) => new Intl.DateTimeFormat('de-DE').format(new Date(value))
</script>
