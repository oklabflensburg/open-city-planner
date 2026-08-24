<template>
  <Card class="p-4">
    <div class="mb-3 flex items-start justify-between gap-3">
      <div><p class="civic-kicker">Branchenmix</p><h2 class="mt-1 text-sm font-extrabold text-[var(--c-text)]">Standorte nach Branche</h2><p class="mt-1 text-[11px] leading-4 text-[var(--c-text-muted)]">Gefilterte Stadtplaner- und deduplizierte OSM-Daten</p></div>
      <Info class="mt-0.5 size-4 shrink-0 text-[var(--c-primary-600)]" aria-hidden="true" />
    </div>
    <div v-if="analytics.loading && !analytics.data" class="h-52 animate-pulse rounded-xl bg-[var(--c-surface-muted)]" />
    <div v-else-if="items.length" class="h-[min(18rem,45vh)] min-h-52"><Bar :data="chartData" :options="chartOptions" :aria-label="accessibleLabel" /></div>
    <p v-else class="rounded-xl bg-[var(--c-surface)] px-3 py-8 text-center text-xs text-[var(--c-text-muted)]">Für die aktuelle Auswahl liegen keine Branchendaten vor.</p>
    <p v-if="items.length" class="mt-2 text-center text-[11px] text-[var(--c-text-muted)]">Gesamt: {{ total.toLocaleString('de-DE') }} Standorte · Balken anklicken zum Filtern</p>
    <table class="sr-only"><caption>Standorte nach Branche</caption><tbody><tr v-for="item in items" :key="item.key"><th>{{ item.label }}</th><td>{{ item.value }}</td></tr></tbody></table>
  </Card>
</template>

<script setup lang="ts">
import { Bar } from 'vue-chartjs'
import type { ActiveElement, ChartEvent, ChartOptions } from 'chart.js'
import { Info } from '@lucide/vue'
import { barChartOptions } from '~/utils/chartTheme'
import { industries, industryColors, type IndustryKey } from '~/utils/industries'

const mapStore = useMapStore()
const analytics = useAnalyticsStore()
const osm = useOsmViewportStore()
const filter = useFilterStore()
const items = computed(() => {
  const counts = new Map<string, number>()
  for (const item of analytics.data?.industry_distribution || []) counts.set(item.category, item.count)
  for (const [key, count] of Object.entries(osm.data?.meta.canonical_summary || {})) counts.set(key, (counts.get(key) || 0) + count)
  return industries.map(industry => ({ key: industry.key, label: industry.label, value: counts.get(industry.key) || 0, color: industryColors[industry.key] })).filter(item => item.value > 0).sort((a, b) => b.value - a.value)
})
const total = computed(() => items.value.reduce((sum, item) => sum + item.value, 0))
const chartData = computed(() => ({ labels: items.value.map(item => item.label), datasets: [{ data: items.value.map(item => item.value), backgroundColor: items.value.map(item => item.color), borderRadius: 5, borderSkipped: false, barThickness: 12 }] }))
const chartOptions = computed<ChartOptions<'bar'>>(() => ({
  ...barChartOptions(true),
  onHover: (_event: ChartEvent, elements: ActiveElement[]) => { mapStore.categoryHighlight = elements[0] ? items.value[elements[0].index]?.key || null : null },
  onClick: (_event: ChartEvent, elements: ActiveElement[]) => { const key = elements[0] ? items.value[elements[0].index]?.key : undefined; if (key) filter.setCategories([key as IndustryKey]) },
}))
const accessibleLabel = computed(() => items.value.map(item => `${item.label}: ${item.value}`).join(', '))
onBeforeUnmount(() => { mapStore.categoryHighlight = null })
</script>
