<template>
  <section v-if="area" :class="embedded ? 'min-w-0 bg-white p-1' : 'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm'" aria-labelledby="analysis-area-title">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-[11px] font-bold uppercase tracking-wide text-[#52758c]">{{ typeLabel(area.area_type) }}</p>
        <h2 id="analysis-area-title" class="mt-1 truncate text-lg font-black text-slate-900">{{ area.name }}</h2>
        <p v-if="area.parent_name" class="mt-1 text-xs text-slate-500">in {{ area.parent_name }}</p>
      </div>
      <button v-if="!embedded" class="grid size-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100" type="button" aria-label="Gebietsauswahl schließen" @click="clearSelection">
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>

    <div v-if="store.detailsLoading" class="mt-4 flex items-center gap-2 text-sm text-slate-500" role="status">
      <LoaderCircle class="size-4 animate-spin" /> Analyse wird berechnet …
    </div>
    <template v-else-if="store.analytics">
      <dl class="mt-4 grid grid-cols-2 gap-2">
        <div v-for="metric in metrics" :key="metric.label" class="rounded-xl bg-slate-50 p-3">
          <dt class="text-[11px] font-semibold text-slate-500">{{ metric.label }}</dt>
          <dd class="mt-1 text-base font-black text-slate-800">{{ metric.value }}</dd>
        </div>
      </dl>
      <div v-if="comparisonRows.length" class="mt-4 border-t border-slate-100 pt-3">
        <p class="text-xs font-bold text-slate-700">Vergleich zur Gesamtstadt</p>
        <div class="mt-2 space-y-2 text-xs">
          <div v-for="row in comparisonRows" :key="row.label" class="flex justify-between gap-3">
            <span class="text-slate-500">{{ row.label }}</span><span class="font-bold text-slate-800">{{ row.value }}</span>
          </div>
        </div>
      </div>
      <div v-if="statisticalMetrics.length" class="mt-4 border-t border-slate-100 pt-3">
        <p class="text-xs font-bold text-slate-700">Kommunale Statistik</p>
        <dl class="mt-2 grid grid-cols-2 gap-2 text-xs">
          <div v-for="item in statisticalMetrics" :key="item.key"><dt class="text-slate-500">{{ item.name }}</dt><dd class="mt-1 font-bold text-slate-800">{{ number.format(Number(item.value)) }}</dd></div>
        </dl>
        <p v-if="store.statistics?.inherited_from_parent" class="mt-2 text-[11px] leading-4 text-slate-500">Stadtteilwert für {{ store.statistics.statistics_area.name }}</p>
      </div>
      <p class="mt-3 text-[11px] leading-4 text-slate-500">OSM-Grenze · admin_level {{ area.source_admin_level ?? '–' }} · Kennzahlen aus räumlich zugeordneten Stadtplaner-Flächen.</p>
      <NuxtLink class="mt-4 inline-flex min-h-10 items-center text-sm font-bold text-[#154d73] underline" :to="`/gebiete/${area.slug}`">
        Gebiet ausführlich ansehen
      </NuxtLink>
    </template>
    <p v-if="store.error" class="mt-3 text-xs text-rose-700">{{ store.error }}</p>
  </section>
</template>

<script setup lang="ts">
import { LoaderCircle, X } from 'lucide-vue-next'
import type { AnalysisAreaType, AreaStatisticValue } from '~/types/analysisArea'

const store = useAnalysisAreasStore()
const mapSelection = useMapSelection()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const embedded = computed(() => props.embedded)
const area = computed(() => store.selectedArea)
const number = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 })
const metrics = computed(() => {
  const data = store.analytics
  if (!data) return []
  return [
    { label: 'Erfasste Flächen', value: number.format(data.metrics.polygon_count) },
    { label: 'Verkaufsfläche', value: data.metrics.total_area_m2 == null ? '–' : `${number.format(data.metrics.total_area_m2)} m²` },
    { label: 'Leerstandsquote', value: data.metrics.vacancy_rate == null ? '–' : `${number.format(data.metrics.vacancy_rate)} %` },
    { label: 'OSM-POIs', value: number.format(data.poi_count) }
  ]
})
const comparisonRows = computed(() => (store.comparison?.differences || [])
  .filter(item => ['vacancy_rate', 'chain_store_rate', 'average_area_m2'].includes(item.key))
  .map(item => ({
    label: item.key === 'vacancy_rate' ? 'Leerstand' : item.key === 'chain_store_rate' ? 'Filialisten' : 'Ø Fläche',
    value: item.difference == null ? '–' : `${item.difference > 0 ? '+' : ''}${number.format(item.difference)} ${item.unit === 'percentage_points' ? 'Prozentpunkte' : 'm²'}`
  })))
const statisticalMetrics = computed(() => ['population', 'households']
  .map(key => store.statistics?.latest.find(item => item.key === key))
  .filter((item): item is AreaStatisticValue => item?.value != null))
function typeLabel(type: AnalysisAreaType) {
  return ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[type]
}
function clearSelection() {
  mapSelection.clearSelection()
}
</script>
