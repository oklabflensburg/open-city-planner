<template>
  <section aria-labelledby="benchmarks-title">
    <div class="flex items-start justify-between gap-3">
      <div><h2 id="benchmarks-title" class="text-xl font-bold text-slate-950">Marktbenchmarks</h2><p class="mt-1 text-sm text-slate-600">{{ analytics.benchmarks?.context_label }}</p></div>
      <button class="page-button-secondary" type="button" :disabled="analytics.benchmarksLoading" @click="analytics.loadBenchmarks()">Aktualisieren</button>
    </div>
    <div v-if="analytics.benchmarksLoading && !analytics.benchmarks" class="mt-5 h-64 animate-pulse rounded-xl bg-slate-100" />
    <div v-else-if="analytics.benchmarksError" class="mt-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-800">Vergleich konnte nicht geladen werden.</div>
    <div v-else-if="analytics.benchmarks" class="mt-5 overflow-x-auto">
      <table class="w-full min-w-[640px] text-left text-sm">
        <thead><tr class="border-b border-slate-200"><th class="py-3 pr-4">Kennzahl</th><th v-for="item in analytics.benchmarks.items" :key="item.key" class="px-4 py-3">{{ item.label }}</th></tr></thead>
        <tbody>
          <tr v-for="metric in metrics" :key="metric.key" class="border-b border-slate-100 last:border-0">
            <th class="py-3 pr-4 font-semibold text-slate-600">{{ metric.label }}</th>
            <td v-for="item in analytics.benchmarks.items" :key="item.key" class="px-4 py-3 tabular-nums">{{ metric.format(item.metrics[metric.key]) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="mt-4 text-xs text-slate-500">Quelle: {{ analytics.benchmarks.source }}<template v-if="dataUpdatedAt"> · Datenstand: {{ dataUpdatedAt }}</template>. Unbekannte Statuswerte werden nicht als belegt oder inhabergeführt gewertet.</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { BenchmarkMetrics } from '~/types/analytics'

const analytics = useAnalyticsStore()
const dataUpdatedAt = computed(() => {
  const values = (analytics.benchmarks?.items || []).map(item => item.metrics.data_updated_at).filter((value): value is string => Boolean(value))
  return values.length ? new Intl.DateTimeFormat('de-DE').format(new Date(values.sort().at(-1)!)) : ''
})
type MetricKey = keyof Pick<BenchmarkMetrics, 'polygon_count' | 'occupied_count' | 'vacant_count' | 'total_area_m2' | 'average_area_m2' | 'median_area_m2' | 'vacancy_rate' | 'chain_store_rate'>
const number = (value: number | null) => value == null ? '—' : Math.round(value).toLocaleString('de-DE')
const percent = (value: number | null) => value == null ? '—' : `${value.toLocaleString('de-DE')} %`
const metrics: Array<{ key: MetricKey, label: string, format: (value: number | null) => string }> = [
  { key: 'polygon_count', label: 'Erfasste Flächen', format: number },
  { key: 'occupied_count', label: 'Belegte Flächen', format: number },
  { key: 'vacant_count', label: 'Leerstände', format: number },
  { key: 'total_area_m2', label: 'Gesamtfläche', format: value => value == null ? '—' : `${number(value)} m²` },
  { key: 'average_area_m2', label: 'Durchschnittsfläche', format: value => value == null ? '—' : `${number(value)} m²` },
  { key: 'median_area_m2', label: 'Medianfläche', format: value => value == null ? '—' : `${number(value)} m²` },
  { key: 'vacancy_rate', label: 'Leerstandsquote', format: percent },
  { key: 'chain_store_rate', label: 'Filialisierungsquote', format: percent }
]
</script>
