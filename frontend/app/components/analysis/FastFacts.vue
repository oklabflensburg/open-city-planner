<template>
  <Card class="p-4">
    <div class="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-bold text-slate-800">Stadtplaner-Kennzahlen</h2>
        <p class="mt-1 text-[11px] text-slate-500">{{ dataStand }}</p>
      </div>
      <span v-if="selectionRestricted" class="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">Aktuelle Auswahl</span>
    </div>
    <div v-if="analytics.loading && !analytics.data" class="facts-grid grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2" aria-label="Kennzahlen werden geladen">
      <div v-for="item in 10" :key="item" class="h-20 animate-pulse rounded-xl bg-slate-100" />
    </div>
    <div v-else-if="analytics.error" class="rounded-xl bg-rose-50 p-3 text-xs text-rose-800">
      <p>Kennzahlen konnten nicht geladen werden.</p>
      <button class="mt-2 cursor-pointer font-bold underline" type="button" @click="analytics.load()">Erneut versuchen</button>
    </div>
    <div v-else-if="fastFacts?.polygon_count === 0 && selectionRestricted" class="mb-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
      <p class="font-bold">Keine gepflegten Stadtplaner-Flächen entsprechen der aktuellen Auswahl.</p>
      <button class="mt-1 min-h-8 cursor-pointer font-bold text-[#154d73] underline" type="button" @click="filter.reset()">Filter zurücksetzen</button>
    </div>
    <div v-else class="facts-grid grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2">
      <div v-for="fact in facts" :key="fact.label" class="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center" :title="fact.available ? fact.description : 'Für diese Kennzahl liegen aktuell keine Daten vor.'">
        <component :is="fact.icon" class="mx-auto mb-1.5 size-4 text-slate-600" aria-hidden="true" />
        <div class="min-h-8 text-[10px] leading-4 text-slate-600">{{ fact.label }}</div>
        <div class="mt-1 whitespace-nowrap text-lg font-light tabular-nums text-slate-800">{{ fact.value }}</div>
        <div class="mt-1 text-[9px] font-bold uppercase tracking-wide text-slate-400">{{ fact.scope }}</div>
      </div>
    </div>
    <NuxtLink class="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-slate-300 px-3 text-xs font-bold text-[#154d73] hover:bg-slate-50" to="/vergleich">Standorte vergleichen</NuxtLink>
  </Card>
</template>

<script setup lang="ts">
import { Building2, Landmark, Maximize2, Network, Ruler, Store, WalletCards } from '@lucide/vue'
import { formatMetricIndex, formatMetricPercent } from '~/utils/metrics'

const analytics = useAnalyticsStore()
const filter = useFilterStore()
const osm = useOsmViewportStore()
const fastFacts = computed(() => analytics.data?.fast_facts)
const selectionRestricted = computed(() => filter.activeFilterCount > 0 || filter.selectedSources.length < 2)
const dataStand = computed(() => {
  const source = fastFacts.value?.source ? ` · Quelle: ${fastFacts.value.source}` : ''
  if (fastFacts.value?.reference_date) {
    return `Stand: ${new Intl.DateTimeFormat('de-DE').format(new Date(`${fastFacts.value.reference_date}T00:00:00`))}${source}`
  }
  if (fastFacts.value?.data_updated_at) {
    return `Flächendaten: ${new Intl.DateTimeFormat('de-DE').format(new Date(fastFacts.value.data_updated_at))}${source}`
  }
  return source ? `Stadtplaner-Daten${source}` : 'Aktuelle Stadtplaner-Auswahl'
})
const facts = computed(() => [
  { label: 'Gefilterte Standorte', value: fastFacts.value?.polygon_count == null ? '—' : (fastFacts.value.polygon_count + (osm.data?.meta.business_count || 0)).toLocaleString('de-DE'), available: fastFacts.value?.polygon_count != null, icon: Store, scope: 'Stadtplaner + OSM', description: 'Deduplizierte Summe aus gepflegten Flächen und passenden OSM-Geschäftsobjekten im Kartenausschnitt.' },
  { label: 'Gepflegte Flächen', value: fastFacts.value?.polygon_count?.toLocaleString('de-DE') ?? '—', available: fastFacts.value?.polygon_count != null, icon: Store, scope: 'Stadtplaner', description: 'Anzahl der aktuell gefilterten Stadtplaner-Flächen.' },
  { label: 'Gesamtfläche', value: fastFacts.value?.total_area_m2 == null ? '—' : `${Math.round(fastFacts.value.total_area_m2).toLocaleString('de-DE')} m²`, available: fastFacts.value?.total_area_m2 != null, icon: Maximize2, scope: 'Auswahl', description: 'Aus den Geometrien der aktuell gefilterten Flächen berechnet.' },
  { label: 'Ø Fläche', value: fastFacts.value?.average_area_m2 == null ? '—' : `${Math.round(fastFacts.value.average_area_m2).toLocaleString('de-DE')} m²`, available: fastFacts.value?.average_area_m2 != null, icon: Maximize2, scope: 'Auswahl', description: 'Aus den Geometrien der aktuell gefilterten Flächen berechnet.' },
  { label: 'Median Fläche', value: fastFacts.value?.median_area_m2 == null ? '—' : `${Math.round(fastFacts.value.median_area_m2).toLocaleString('de-DE')} m²`, available: fastFacts.value?.median_area_m2 != null, icon: Ruler, scope: 'Auswahl', description: 'Robuster mittlerer Flächenwert der aktuellen Auswahl.' },
  { label: 'Leerstandsfläche', value: fastFacts.value?.vacant_area_m2 == null ? '—' : `${Math.round(fastFacts.value.vacant_area_m2).toLocaleString('de-DE')} m²`, available: fastFacts.value?.vacant_area_m2 != null, icon: Landmark, scope: 'Auswahl', description: fastFacts.value?.vacancy_area_rate == null ? 'Fläche der als leerstehend markierten Objekte.' : `${fastFacts.value.vacancy_area_rate.toLocaleString('de-DE')} % der Fläche mit bekanntem Status.` },
  { label: 'Leerstand', value: formatMetricPercent(vacancyValue.value), available: vacancyValue.value != null, icon: Landmark, scope: selectionRestricted.value ? 'Auswahl' : 'Auswahl/Stadt', description: fastFacts.value?.calculated_vacancy_rate != null ? `Berechnet aus ${fastFacts.value.known_occupancy_count} Flächen mit bekanntem Status.` : 'Manuell gepflegte Stadtkennzahl.' },
  { label: 'Filialisierung', value: formatMetricPercent(chainValue.value), available: chainValue.value != null, icon: Network, scope: selectionRestricted.value ? 'Auswahl' : 'Auswahl/Stadt', description: fastFacts.value?.calculated_chain_store_rate != null ? `Berechnet aus ${fastFacts.value.known_business_structure_count} Flächen mit bekannter Betriebsform.` : 'Manuell gepflegte Stadtkennzahl.' },
  { label: 'Zentralität (Index)', value: formatMetricIndex(fastFacts.value?.centrality_index), available: fastFacts.value?.centrality_index != null, icon: Building2, scope: 'Stadtwert', description: 'Manuell gepflegter Referenzwert für die Gesamtstadt; nicht durch Flächenfilter neu berechnet.' },
  { label: 'Kaufkraft (Index)', value: formatMetricIndex(fastFacts.value?.purchasing_power_index), available: fastFacts.value?.purchasing_power_index != null, icon: WalletCards, scope: 'Stadtwert', description: 'Manuell gepflegter Referenzwert für die Gesamtstadt; nicht durch Flächenfilter neu berechnet.' }
])
const vacancyValue = computed(() => selectionRestricted.value ? fastFacts.value?.calculated_vacancy_rate : (fastFacts.value?.calculated_vacancy_rate ?? fastFacts.value?.vacancy_rate))
const chainValue = computed(() => selectionRestricted.value ? fastFacts.value?.calculated_chain_store_rate : (fastFacts.value?.calculated_chain_store_rate ?? fastFacts.value?.chain_store_rate))

</script>
