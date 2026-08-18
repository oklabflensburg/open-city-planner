<template>
  <section aria-labelledby="comparison-charts-title">
    <div><p class="civic-kicker">Visualisierung</p><h2 id="comparison-charts-title" class="mt-1 text-xl font-black text-slate-950">Unterschiede auf einen Blick</h2></div>
    <div class="mt-4 grid min-w-0 gap-4 xl:grid-cols-2">
      <Card class="min-w-0 overflow-hidden p-4"><h3 class="text-sm font-black text-slate-900">Erfasste Flächen</h3><div class="mt-3 h-64 min-w-0"><Bar :data="countData" :options="barChartOptions()" aria-label="Erfasste Flächen nach Gebiet" /></div></Card>
      <Card class="min-w-0 overflow-hidden p-4"><h3 class="text-sm font-black text-slate-900">Leerstandsquote</h3><div v-if="hasVacancyData" class="mt-3 h-64 min-w-0"><Bar :data="vacancyData" :options="percentOptions" aria-label="Leerstandsquote nach Gebiet" /></div><p v-else class="mt-3 py-20 text-center text-sm text-slate-500">Keine berechenbaren Leerstandsquoten verfügbar.</p></Card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Bar } from 'vue-chartjs'
import type { ChartOptions } from 'chart.js'
import type { AreaCompareItem } from '~/types/analytics'
import { barChartOptions } from '~/utils/chartTheme'

const props = defineProps<{ items: Array<AreaCompareItem & { benchmark?: boolean }>, colors: string[] }>()
const countData = computed(() => ({ labels: props.items.map(item => item.name), datasets: [{ label: 'Flächen', data: props.items.map(item => item.metrics.polygon_count), backgroundColor: props.colors, borderRadius: 5, borderSkipped: false }] }))
const vacancyData = computed(() => ({ labels: props.items.map(item => item.name), datasets: [{ label: 'Leerstandsquote in %', data: props.items.map(item => item.metrics.vacancy_rate), backgroundColor: props.colors, borderRadius: 5, borderSkipped: false }] }))
const hasVacancyData = computed(() => props.items.some(item => item.metrics.vacancy_rate != null))
const percentOptions: ChartOptions<'bar'> = { ...barChartOptions(), scales: { x: { beginAtZero: true }, y: { beginAtZero: true, ticks: { callback: value => `${value} %` } } } }
</script>
