<template>
  <section class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="kommunale-statistik">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div><p class="text-xs font-black uppercase tracking-widest text-[#154d73]">Stadt Flensburg</p><h2 id="kommunale-statistik" class="mt-1 text-2xl font-black text-slate-950">Kommunale Statistik</h2></div>
      <OcpStatusBadge tone="info">{{ levelLabel }}</OcpStatusBadge>
    </div>

    <div v-if="statistics.inherited_from_parent" class="mt-5 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-950">
      Für dieses Quartier liegen keine eigenen Zahlenspiegel-Werte vor. Die folgenden Daten beziehen sich auf den gesamten Stadtteil
      <NuxtLink class="font-bold underline" :to="`/gebiete/${statistics.statistics_area.slug}`">{{ statistics.statistics_area.name }}</NuxtLink>.
    </div>

    <p v-if="!statistics.latest.length" class="mt-5 text-slate-600">Für dieses Gebiet wurden noch keine kommunalen Statistiken importiert.</p>
    <template v-else>
      <dl class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="item in highlights" :key="item.key" class="rounded-xl bg-slate-50 p-4">
          <dt class="text-sm font-semibold text-slate-600">{{ item.name }}</dt>
          <dd class="mt-2 text-2xl font-black text-slate-950">{{ formatValue(item.value, item.unit) }}</dd>
          <p class="mt-1 text-xs text-slate-500">Stand {{ item.period }}</p>
          <p v-if="comparisonText(item)" class="mt-2 text-xs leading-5 text-slate-600">{{ comparisonText(item) }}</p>
        </div>
      </dl>

      <div v-if="series.series.length" class="mt-7 border-t border-slate-200 pt-6">
        <h3 class="font-black text-slate-950">{{ series.metric.name }} im Zeitverlauf</h3>
        <div class="mt-3 overflow-x-auto rounded-xl border border-slate-200">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-slate-50"><tr><th v-for="point in recentSeries" :key="point.period" scope="col" class="px-4 py-3">{{ point.period }}</th></tr></thead>
            <tbody><tr><td v-for="point in recentSeries" :key="point.period" class="px-4 py-3 font-bold">{{ formatValue(point.value, series.metric.unit) }}</td></tr></tbody>
          </table>
        </div>
      </div>

      <details class="mt-7 border-t border-slate-200 pt-6">
        <summary class="cursor-pointer font-black text-[#154d73]">Alle {{ statistics.latest.length }} Kennzahlen anzeigen</summary>
        <div v-for="group in groups" :key="group.category" class="mt-6">
          <h3 class="font-black text-slate-950">{{ group.category }}</h3>
          <dl class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div v-for="item in group.items" :key="item.key" class="rounded-xl border border-slate-200 p-4">
              <dt class="text-sm text-slate-600">{{ item.name }}</dt><dd class="mt-1 font-black">{{ formatValue(item.value, item.unit) }}</dd><p class="mt-1 text-xs text-slate-500">{{ item.period }}</p>
            </div>
          </dl>
        </div>
      </details>
    </template>

    <footer v-if="statistics.source" class="mt-7 border-t border-slate-200 pt-5 text-sm leading-6 text-slate-600">
      <p><strong>Datenquelle:</strong> <a class="font-bold text-[#154d73] underline" :href="statistics.source.url" target="_blank" rel="noopener noreferrer">{{ statistics.source.name }}</a></p>
      <p>Datenstand: {{ latestPeriod }} · Letzter Import: {{ formatDate(statistics.source.last_import_at) }}</p>
      <p>Lizenz: {{ statistics.source.license }}</p>
      <p class="mt-2 text-xs">Die statistischen Werte sind über ein geprüftes Mapping den gleichnamigen Stadtteilen zugeordnet. Die dargestellten OpenStreetMap-Grenzen sind nicht als geometrisch exakte Übereinstimmung mit der kommunalen Statistikgeografie zu verstehen.</p>
    </footer>
  </section>
</template>

<script setup lang="ts">
import type { AreaStatisticSeries, AreaStatistics, AreaStatisticValue } from '~/types/analysisArea'
import { OcpStatusBadge } from '#frontend-module-sdk/ui'

const props = defineProps<{ statistics: AreaStatistics, series: AreaStatisticSeries }>()
const priority = ['population', 'population_non_german', 'population_age_0_17', 'population_age_65_plus', 'households', 'households_non_german']
const highlights = computed(() => priority.map(key => props.statistics.latest.find(item => item.key === key)).filter((item): item is AreaStatisticValue => Boolean(item)))
const groups = computed(() => [...new Set(props.statistics.latest.map(item => item.category))].map(category => ({ category, items: props.statistics.latest.filter(item => item.category === category) })))
const recentSeries = computed(() => props.series.series.slice(-6))
const latestPeriod = computed(() => props.statistics.latest.map(item => item.period).sort().at(-1) || '—')
const levelLabel = computed(() => props.statistics.inherited_from_parent ? `Stadtteilwert · ${props.statistics.statistics_area.name}` : ({ MUNICIPALITY: 'Gesamtstadt', DISTRICT: 'Stadtteilwert', QUARTER: 'Quartierswert' })[props.statistics.statistics_area.area_type])
const numberFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 })
function formatValue(value: number | string | null, unit: string) { return value == null ? '—' : `${numberFormat.format(Number(value))}${unit === 'percent' ? ' %' : ''}` }
function comparisonText(item: AreaStatisticValue) {
  if (props.statistics.statistics_area.area_type === 'MUNICIPALITY' || item.relative_difference == null) return ''
  const difference = Number(item.relative_difference)
  if (difference === 0) return 'Entspricht dem rechnerischen Gesamtstadtwert.'
  return `${numberFormat.format(Math.abs(difference))} % ${difference > 0 ? 'über' : 'unter'} dem rechnerischen Gesamtstadtwert.`
}
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(new Date(value)) : '—' }
</script>
