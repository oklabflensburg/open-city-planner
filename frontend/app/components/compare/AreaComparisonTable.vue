<template>
  <section aria-labelledby="comparison-table-title">
    <div><p class="civic-kicker">Direkter Vergleich</p><h2 id="comparison-table-title" class="mt-1 text-xl font-black text-slate-950">Kennzahlen</h2></div>
    <div class="mt-4 max-w-full overflow-x-auto rounded-2xl border border-slate-200">
      <table class="w-full min-w-[720px] border-separate border-spacing-0 text-left text-sm">
        <thead>
          <tr>
            <th class="sticky left-0 z-10 border-b border-slate-200 bg-white px-4 py-3">Kennzahl</th>
            <th v-for="(item, index) in items" :key="item.slug" class="border-b border-slate-200 px-4 py-3" :class="item.benchmark ? 'bg-slate-100' : 'bg-white'">
              <span class="flex items-center gap-2"><span class="size-2.5 rounded-full" :style="{ backgroundColor: colors[index] }" aria-hidden="true" /><span>{{ item.name }}</span></span>
              <span class="mt-1 block text-[10px] font-bold uppercase tracking-wide text-slate-500">{{ item.benchmark ? 'Referenz' : typeLabel(item.area_type) }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="metric in metrics" :key="metric.key">
            <th class="sticky left-0 z-10 border-b border-slate-100 bg-white px-4 py-3 font-semibold text-slate-600">{{ metric.label }}</th>
            <td v-for="item in items" :key="item.slug" class="border-b border-slate-100 px-4 py-3 align-top tabular-nums" :class="item.benchmark ? 'bg-slate-50' : 'bg-white'">
              <span v-if="metricValue(item, metric) == null" title="Kein Wert verfügbar">—</span>
              <template v-else>
                <strong class="text-slate-950">{{ formattedValue(item, metric) }}</strong>
                <span v-if="difference(item, metric)" class="mt-1 block text-[11px] text-slate-500">{{ difference(item, metric) }}</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AreaCompareItem, AreaCompareMetrics } from '~/types/analytics'

type DisplayItem = AreaCompareItem & { benchmark?: boolean }
type MetricKey = keyof Pick<AreaCompareMetrics, 'polygon_count' | 'occupied_count' | 'vacant_count' | 'vacancy_rate' | 'total_area_m2' | 'average_area_m2' | 'median_area_m2' | 'chain_store_rate' | 'locations_per_km2' | 'retail_area_m2_per_km2'>
const props = defineProps<{ items: DisplayItem[], colors: string[] }>()
const benchmark = computed(() => props.items.find(item => item.benchmark))
const number = (value: number) => Math.round(value).toLocaleString('de-DE')
const percent = (value: number) => `${value.toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`
const metrics: Array<{ key: MetricKey, label: string, format: (value: number) => string, difference?: 'percentage_points' }> = [
  { key: 'polygon_count', label: 'Erfasste Flächen', format: number },
  { key: 'occupied_count', label: 'Belegte Flächen', format: number },
  { key: 'vacant_count', label: 'Leerstände', format: number },
  { key: 'vacancy_rate', label: 'Leerstandsquote', format: percent, difference: 'percentage_points' },
  { key: 'total_area_m2', label: 'Gesamtfläche', format: value => `${number(value)} m²` },
  { key: 'average_area_m2', label: 'Durchschnittsfläche', format: value => `${number(value)} m²` },
  { key: 'median_area_m2', label: 'Medianfläche', format: value => `${number(value)} m²` },
  { key: 'chain_store_rate', label: 'Filialisierungsquote', format: percent, difference: 'percentage_points' },
  { key: 'locations_per_km2', label: 'Flächen pro km²', format: number },
  { key: 'retail_area_m2_per_km2', label: 'Verkaufsfläche pro km²', format: value => `${number(value)} m²/km²` }
]
function typeLabel(type: AreaCompareItem['area_type']) {
  return ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[type]
}
function metricValue(item: DisplayItem, metric: typeof metrics[number]) {
  return item.metrics[metric.key]
}
function formattedValue(item: DisplayItem, metric: typeof metrics[number]) {
  const value = metricValue(item, metric)
  return value == null ? '—' : metric.format(value)
}
function difference(item: DisplayItem, metric: typeof metrics[number]) {
  if (!metric.difference || item.benchmark || !benchmark.value) return ''
  const value = item.metrics[metric.key]
  const reference = benchmark.value.metrics[metric.key]
  if (value == null || reference == null) return ''
  const delta = Number(value) - Number(reference)
  if (delta === 0) return 'entspricht der Referenz'
  const sign = delta > 0 ? '+' : '−'
  return `${sign}${Math.abs(delta).toLocaleString('de-DE', { maximumFractionDigits: 1 })} Prozentpunkte ggü. Gesamtstadt`
}
</script>
