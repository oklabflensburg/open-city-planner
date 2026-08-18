<template>
  <Card class="p-4">
    <div><p class="civic-kicker">Struktur &amp; Datenqualität</p><h2 class="mt-1 text-sm font-extrabold text-[var(--c-text)]">Gefilterte Flächen im Überblick</h2><p class="mt-1 text-[11px] text-[var(--c-text-muted)]">Berechnet aus gepflegten Stadtplaner-Flächen</p></div>
    <div class="mt-3 flex gap-1 overflow-x-auto rounded-xl bg-[var(--c-surface-muted)] p-1" role="tablist" aria-label="Diagramm auswählen">
      <button v-for="tab in tabs" :key="tab.key" class="min-h-9 shrink-0 cursor-pointer rounded-lg px-2.5 text-[11px] font-bold transition" :class="activeTab === tab.key ? 'bg-white text-[var(--c-primary-800)] shadow-sm' : 'text-[var(--c-text-muted)] hover:text-[var(--c-text)]'" type="button" role="tab" :aria-selected="activeTab === tab.key" @click="activeTab = tab.key">{{ tab.label }}</button>
    </div>
    <div v-if="analytics.loading && !analytics.data" class="mt-3 h-48 animate-pulse rounded-xl bg-[var(--c-surface-muted)]" />
    <div v-else-if="values.some(value => value > 0)" class="mt-3 h-52">
      <Doughnut v-if="isDoughnut" :data="chartData" :options="doughnutChartOptions()" :aria-label="accessibleLabel" />
      <Bar v-else :data="chartData" :options="barChartOptions(activeTab === 'quality')" :aria-label="accessibleLabel" />
    </div>
    <p v-else class="mt-3 rounded-xl bg-[var(--c-surface)] px-3 py-8 text-center text-xs text-[var(--c-text-muted)]">Für diese Auswertung liegen keine Angaben vor.</p>
    <table class="sr-only"><caption>{{ activeLabel }}</caption><tbody><tr v-for="(label, index) in labels" :key="label"><th>{{ label }}</th><td>{{ values[index] }}</td></tr></tbody></table>
  </Card>
</template>

<script setup lang="ts">
import { Bar, Doughnut } from 'vue-chartjs'
import { barChartOptions, chartPalette, chartSeries, doughnutChartOptions } from '~/utils/chartTheme'

type TabKey = 'size' | 'floor' | 'status' | 'business' | 'quality'
const analytics = useAnalyticsStore()
const activeTab = ref<TabKey>('status')
const tabs: Array<{ key: TabKey, label: string }> = [
  { key: 'size', label: 'Größe' }, { key: 'floor', label: 'Etage' }, { key: 'status', label: 'Status' },
  { key: 'business', label: 'Betrieb' }, { key: 'quality', label: 'Qualität' },
]
const activeLabel = computed(() => tabs.find(tab => tab.key === activeTab.value)?.label || '')
const distribution = computed(() => {
  if (activeTab.value === 'size') return analytics.data?.size_distribution || []
  if (activeTab.value === 'floor') return analytics.data?.floor_distribution || []
  if (activeTab.value === 'status') return analytics.data?.status_distribution || []
  if (activeTab.value === 'business') return analytics.data?.business_structure_distribution || []
  return (analytics.data?.data_completeness || []).map(item => ({ key: item.key, label: item.label, count: item.percent || 0 }))
})
const labels = computed(() => distribution.value.map(item => item.label))
const values = computed(() => distribution.value.map(item => item.count))
const isDoughnut = computed(() => activeTab.value === 'status' || activeTab.value === 'business')
const chartData = computed(() => ({
  labels: labels.value,
  datasets: [{ label: activeTab.value === 'quality' ? 'Vollständigkeit in %' : 'Flächen', data: values.value,
    backgroundColor: activeTab.value === 'status' ? [chartPalette.green, chartPalette.danger, chartPalette.muted] : activeTab.value === 'business' ? [chartPalette.blue, chartPalette.secondary, chartPalette.muted] : chartSeries,
    borderWidth: isDoughnut.value ? 2 : 0, borderColor: '#fff', borderRadius: isDoughnut.value ? 0 : 5, borderSkipped: false }],
}))
const accessibleLabel = computed(() => `${activeLabel.value}: ${labels.value.map((label, index) => `${label} ${values.value[index]}${activeTab.value === 'quality' ? ' Prozent' : ''}`).join(', ')}`)
</script>
