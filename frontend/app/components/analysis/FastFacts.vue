<template>
  <Card class="p-4">
    <div class="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-bold text-slate-800">Kennzahlen</h2>
        <p class="mt-1 text-[11px] text-slate-500">{{ dataStand }}</p>
      </div>
      <div class="flex items-center gap-1">
        <button class="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" aria-label="Kennzahlen aktualisieren" :disabled="analytics.loading" @click="analytics.load()">
          <RefreshCw class="size-4" :class="{ 'animate-spin': analytics.loading }" />
        </button>
      </div>
    </div>
    <div v-if="analytics.loading && !analytics.data" class="facts-grid grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2" aria-label="Kennzahlen werden geladen">
      <div v-for="item in 5" :key="item" class="h-20 animate-pulse rounded-xl bg-slate-100" />
    </div>
    <div v-else-if="analytics.error" class="rounded-xl bg-rose-50 p-3 text-xs text-rose-800">
      <p>Kennzahlen konnten nicht geladen werden.</p>
      <button class="mt-2 font-bold underline" type="button" @click="analytics.load()">Erneut versuchen</button>
    </div>
    <div v-else class="facts-grid grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2">
      <div v-for="fact in facts" :key="fact.label" class="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center" :title="fact.available ? fact.description : 'Für diese Kennzahl liegen aktuell keine Daten vor.'">
        <component :is="fact.icon" class="mx-auto mb-1.5 size-4 text-slate-600" aria-hidden="true" />
        <div class="min-h-8 text-[10px] leading-4 text-slate-600">{{ fact.label }}</div>
        <div class="mt-1 text-xl font-light tabular-nums text-slate-800">{{ fact.value }}</div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { Building2, Landmark, Network, RefreshCw, Store, WalletCards } from 'lucide-vue-next'
import { formatMetricIndex, formatMetricPercent } from '~/utils/metrics'

const analytics = useAnalyticsStore()
const fastFacts = computed(() => analytics.data?.fast_facts)
const dataStand = computed(() => {
  if (fastFacts.value?.reference_date) {
    return `Stand: ${new Intl.DateTimeFormat('de-DE').format(new Date(`${fastFacts.value.reference_date}T00:00:00`))}`
  }
  return fastFacts.value?.updated_at
    ? `Zuletzt aktualisiert: ${new Intl.DateTimeFormat('de-DE', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(fastFacts.value.updated_at))} Uhr`
    : 'Kein Datenstand verfügbar'
})
const facts = computed(() => [
  { label: 'Shops', value: fastFacts.value?.shops?.toLocaleString('de-DE') ?? '—', available: fastFacts.value?.shops != null, icon: Store, description: 'Öffentliche Flächen in gepflegten Handels-, Gastronomie- und Dienstleistungskategorien.' },
  { label: 'Leerstand', value: formatMetricPercent(fastFacts.value?.vacancy_rate), available: fastFacts.value?.vacancy_rate != null, icon: Landmark, description: '' },
  { label: 'Filialisierung', value: formatMetricPercent(fastFacts.value?.chain_store_rate), available: fastFacts.value?.chain_store_rate != null, icon: Network, description: '' },
  { label: 'Zentralität (Index)', value: formatMetricIndex(fastFacts.value?.centrality_index), available: fastFacts.value?.centrality_index != null, icon: Building2, description: '' },
  { label: 'Kaufkraft (Index)', value: formatMetricIndex(fastFacts.value?.purchasing_power_index), available: fastFacts.value?.purchasing_power_index != null, icon: WalletCards, description: '' }
])

</script>

<style scoped>
@media (min-width: 1440px) {
  .facts-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
