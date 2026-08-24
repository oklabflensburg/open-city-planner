<template>
  <ContentPageShell
    title="Gebiete vergleichen"
    description="Vergleichen Sie Gemeinden, Stadtteile und Quartiere anhand derselben Stadtplaner-Kennzahlen."
    eyebrow="Marktanalyse"
    :breadcrumbs="[{ label: 'Karte', to: '/karte' }, { label: 'Vergleich' }]"
    max-width="wide"
  >
    <div class="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)]">
      <Card class="min-w-0 p-5 lg:sticky lg:top-24">
        <AreaComparisonSelector
          :areas="comparison.availableAreas"
          :selected-slugs="selectedSlugs"
          :colors="comparisonColors"
          :loading="comparison.areasLoading"
          :error="comparison.areasError"
          @add="addArea"
          @remove="removeArea"
        />

        <section class="mt-6 border-t border-slate-200 pt-5" aria-labelledby="comparison-reference-title">
          <h2 id="comparison-reference-title" class="text-xs font-black uppercase tracking-wide text-slate-600">Referenz</h2>
          <GisFilterToggleRow v-model="benchmarkEnabled" class="mt-2" label="Gesamtstadt einblenden" aria-label="Gesamtstadt als Referenz anzeigen" :disabled="hasSelectedMunicipality" />
          <p class="mt-1 text-xs leading-5 text-slate-500">{{ hasSelectedMunicipality ? 'Die Gemeinde ist bereits als Vergleichsgebiet gewählt.' : 'Zeigt den Flensburger Gesamtwert unter denselben Filtern.' }}</p>
        </section>

        <details class="mt-6 border-t border-slate-200 pt-5">
          <summary class="min-h-11 cursor-pointer text-sm font-black text-[#154d73]">Vergleich einschränken</summary>
          <p class="mb-5 text-xs leading-5 text-slate-500">Diese Filter gelten fair und identisch für alle Vergleichsgebiete.</p>
          <div class="space-y-6"><AreaFilter /><FloorFilter /><IndustryFilter /><MarketStatusFilter /><DataSourceFilter /></div>
        </details>
      </Card>

      <main class="min-w-0" aria-live="polite">
        <div v-if="comparison.error" class="rounded-2xl bg-rose-50 p-5 text-sm text-rose-800">{{ comparison.error }}</div>
        <div v-if="comparison.result?.ignored_slugs.length" class="mb-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Nicht gefundene Gebiete wurden ignoriert: {{ comparison.result.ignored_slugs.join(', ') }}.</div>

        <Card v-if="!selectedSlugs.length" class="px-6 py-14 text-center sm:px-10">
          <MapPinned class="mx-auto size-10 text-[#154d73]" aria-hidden="true" />
          <h2 class="mt-4 text-2xl font-black text-slate-950">Welche Gebiete möchten Sie vergleichen?</h2>
          <p class="mx-auto mt-3 max-w-xl leading-7 text-slate-600">Wählen Sie Gemeinden, Stadtteile oder Quartiere aus. Bis zu vier konkrete Gebiete können gemeinsam betrachtet werden.</p>
          <button class="page-button-primary mt-6" type="button" @click="focusAreaSearch">Gebiet auswählen</button>
        </Card>

        <Card v-else-if="!comparisonReady && !comparison.loading" class="px-6 py-12 text-center">
          <h2 class="text-xl font-black text-slate-950">Weiteres Gebiet hinzufügen</h2>
          <p class="mt-2 text-slate-600">Ein Vergleich benötigt mindestens zwei Gebiete oder ein Gebiet mit Gesamtstadt-Referenz.</p>
        </Card>

        <div v-if="comparison.loading && !comparison.result" class="space-y-4" aria-label="Vergleich wird geladen">
          <div class="h-40 animate-pulse rounded-2xl bg-slate-100" /><div class="h-96 animate-pulse rounded-2xl bg-slate-100" />
        </div>

        <div v-if="comparisonReady" class="space-y-8" :class="{ 'opacity-60': comparison.loading }" :aria-busy="comparison.loading">
          <section aria-labelledby="comparison-overview-title">
            <div><p class="civic-kicker">Ausgewählte Gebiete</p><h2 id="comparison-overview-title" class="mt-1 text-xl font-black text-slate-950">Vergleichspartner</h2></div>
            <div class="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Card v-for="(item, index) in displayItems" :key="item.slug" class="overflow-hidden">
                <div class="h-1.5" :style="{ backgroundColor: displayColors[index] }" />
                <div class="p-4">
                  <div class="flex items-start justify-between gap-3"><div><h3 class="font-black text-slate-950">{{ item.name }}</h3><p class="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">{{ item.benchmark ? 'Referenz · Gesamtstadt' : typeLabel(item.area_type) }}</p></div><span v-if="item.benchmark" class="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-black text-slate-600">Referenz</span></div>
                  <dl class="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt class="text-xs text-slate-500">Flächen</dt><dd class="mt-1 font-black">{{ formatNumber(item.metrics.polygon_count) }}</dd></div><div><dt class="text-xs text-slate-500">Leerstand</dt><dd class="mt-1 font-black">{{ formatPercent(item.metrics.vacancy_rate) }}</dd></div></dl>
                  <p v-if="item.metrics.polygon_count === 0" class="mt-3 text-xs leading-5 text-slate-500">Keine passenden Flächendaten vorhanden.</p>
                  <NuxtLink class="mt-4 inline-flex min-h-10 items-center font-bold text-[#154d73] underline" :to="`/gebiete/${item.slug}`">Gebiet ansehen</NuxtLink>
                </div>
              </Card>
            </div>
          </section>

          <AreaComparisonCharts :items="displayItems" :colors="displayColors" />
          <AreaComparisonTable :items="displayItems" :colors="displayColors" />
          <p class="text-xs leading-5 text-slate-500">Quelle: {{ comparison.result?.source }}. Quoten verwenden nur Flächen mit bekanntem Status. Ein Gedankenstrich bedeutet „kein Wert verfügbar“, nicht null.</p>
        </div>
      </main>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { MapPinned } from '@lucide/vue'
import type { AnalysisAreaType } from '~/types/analysisArea'

const route = useRoute()
const comparison = useComparisonStore()
const filter = useFilterStore()
const selectedSlugs = ref<string[]>([])
const benchmarkEnabled = ref(true)
const comparisonColors = ['#086b78', '#2f87b7', '#4f9b62', '#dcae45']
const benchmarkColor = '#64748b'
let compareTimer: ReturnType<typeof setTimeout> | undefined
let applyingLocation = false
useGisFilterHistory()

const selectedAreas = computed(() => selectedSlugs.value.flatMap(slug => {
  const area = comparison.availableAreas.find(candidate => candidate.slug === slug)
  return area ? [area] : []
}))
const hasSelectedMunicipality = computed(() => selectedAreas.value.some(area => area.area_type === 'MUNICIPALITY'))
const effectiveBenchmark = computed(() => benchmarkEnabled.value && !hasSelectedMunicipality.value)
const displayItems = computed(() => [
  ...(comparison.result?.areas || []).map(item => ({ ...item, benchmark: false })),
  ...(comparison.result?.benchmark ? [{ ...comparison.result.benchmark, benchmark: true }] : [])
])
const displayColors = computed(() => [...comparisonColors.slice(0, comparison.result?.areas.length || 0), ...(comparison.result?.benchmark ? [benchmarkColor] : [])])
const comparisonReady = computed(() => displayItems.value.length >= 2)

function querySlugs() {
  const params = import.meta.client ? new URLSearchParams(window.location.search) : null
  const raw = params?.get('gebiete') ?? params?.get('areas') ?? params?.get('area') ?? route.query.gebiete ?? route.query.areas ?? route.query.area
  const value = Array.isArray(raw) ? raw.join(',') : String(raw || '')
  return [...new Set(value.split(',').map(item => item.trim().toLocaleLowerCase('de-DE')).filter(Boolean))].slice(0, 4)
}
function applyLocation() {
  applyingLocation = true
  selectedSlugs.value = querySlugs()
  benchmarkEnabled.value = (import.meta.client ? new URLSearchParams(window.location.search).get('benchmark') : route.query.benchmark) !== '0'
  nextTick(() => { applyingLocation = false })
}
function syncUrl() {
  if (!import.meta.client || applyingLocation) return
  const url = new URL(window.location.href)
  if (selectedSlugs.value.length) url.searchParams.set('gebiete', selectedSlugs.value.join(','))
  else url.searchParams.delete('gebiete')
  url.searchParams.delete('areas')
  url.searchParams.delete('area')
  if (benchmarkEnabled.value) url.searchParams.delete('benchmark')
  else url.searchParams.set('benchmark', '0')
  window.history.pushState({ ...window.history.state }, '', url)
}
function scheduleComparison() {
  clearTimeout(compareTimer)
  compareTimer = setTimeout(() => void comparison.compare(selectedSlugs.value, effectiveBenchmark.value), 180)
}
function addArea(slug: string) {
  if (selectedSlugs.value.length >= 4 || selectedSlugs.value.includes(slug)) return
  selectedSlugs.value = [...selectedSlugs.value, slug]
}
function removeArea(slug: string) {
  selectedSlugs.value = selectedSlugs.value.filter(item => item !== slug)
}
function focusAreaSearch() {
  document.querySelector<HTMLInputElement>('#compare-area-search')?.focus()
}
function typeLabel(type: AnalysisAreaType) {
  return ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[type]
}
function formatNumber(value: number | null) {
  return value == null ? '—' : Math.round(value).toLocaleString('de-DE')
}
function formatPercent(value: number | null) {
  return value == null ? '—' : `${value.toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`
}

onMounted(async () => {
  applyLocation()
  window.addEventListener('popstate', applyLocation)
  await comparison.loadAreas()
  scheduleComparison()
})
watch([selectedSlugs, benchmarkEnabled, () => filter.filterKey], () => {
  syncUrl()
  scheduleComparison()
}, { deep: true })
onBeforeUnmount(() => {
  clearTimeout(compareTimer)
  window.removeEventListener('popstate', applyLocation)
  comparison.reset()
})

usePageSeo({ title: 'Gebiete vergleichen', description: 'Gemeinden, Stadtteile und Quartiere anhand derselben Stadtplaner-Kennzahlen vergleichen.', path: '/vergleich' })
</script>
