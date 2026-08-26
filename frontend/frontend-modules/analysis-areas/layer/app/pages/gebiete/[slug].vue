<template>
  <ContentPageShell
    :title="area.name"
    :description="`${typeLabel} mit aktuellen Standort- und Einzelhandelsdaten aus Stadtplaner.`"
    :eyebrow="typeLabel"
    :breadcrumbs="breadcrumbs"
    max-width="wide"
  >
    <template #actions>
      <div class="flex flex-wrap gap-2">
        <NotificationFollowButton v-if="authStore.authenticated" resource-type="AREA" :resource-id="area.id" follow-label="Diesem Gebiet folgen" followed-label="Sie folgen diesem Gebiet" />
        <NuxtLink class="inline-flex min-h-11 items-center rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-[#154d73] hover:bg-slate-50" :to="`/vergleich?gebiete=${encodeURIComponent(area.slug)}`">Mit anderem Gebiet vergleichen</NuxtLink>
        <NuxtLink class="inline-flex min-h-11 items-center rounded-xl bg-[#154d73] px-4 text-sm font-bold text-white hover:bg-[#103c59]" :to="{ path: '/karte', query: { gebiet: area.slug } }">In der Karte öffnen</NuxtLink>
      </div>
    </template>

    <section
      v-if="socialPreview"
      data-social-preview-capture
      :data-social-preview-ready="previewReady ? 'true' : 'false'"
      class="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50 p-6"
    >
      <div v-if="previewBranding" class="mb-5 flex items-center justify-between gap-4">
        <div><p class="text-sm font-black uppercase tracking-widest text-[#154d73]">Stadtplaner</p><p class="text-sm text-slate-600">OK Lab Flensburg</p></div>
        <p class="rounded-full bg-[#154d73] px-4 py-2 text-sm font-bold text-white">{{ typeLabel }}</p>
      </div>
      <h1 class="text-4xl font-black text-slate-950">{{ area.name }}</h1>
      <dl v-if="previewFacts" class="my-5 grid grid-cols-4 gap-3">
        <div class="rounded-xl bg-white p-3"><dt class="text-xs font-bold text-slate-500">Flächen</dt><dd class="mt-1 text-xl font-black">{{ formatNumber(analytics.metrics.polygon_count) }}</dd></div>
        <div class="rounded-xl bg-white p-3"><dt class="text-xs font-bold text-slate-500">Leerstand</dt><dd class="mt-1 text-xl font-black">{{ formatPercent(analytics.metrics.vacancy_rate) }}</dd></div>
        <div class="rounded-xl bg-white p-3"><dt class="text-xs font-bold text-slate-500">Gesamtfläche</dt><dd class="mt-1 text-xl font-black">{{ formatSquareMetres(analytics.metrics.total_area_m2) }}</dd></div>
        <div class="rounded-xl bg-white p-3"><dt class="text-xs font-bold text-slate-500">Orte</dt><dd class="mt-1 text-xl font-black">{{ previewPois ? formatNumber(analytics.poi_count) : '–' }}</dd></div>
      </dl>
      <AnalysisAreaDetailMap v-if="previewMap" :area="area" @ready="mapReady = true" />
    </section>

    <template v-else>

    <section aria-labelledby="kennzahlen">
      <h2 id="kennzahlen" class="text-2xl font-black text-slate-950">Kennzahlen</h2>
      <dl class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><PolygonMetricCard label="Erfasste Flächen" :value="formatNumber(analytics.metrics.polygon_count)" /></div>
        <div><PolygonMetricCard label="Gesamtfläche" :value="formatSquareMetres(analytics.metrics.total_area_m2)" /></div>
        <div><PolygonMetricCard label="Leerstandsquote" :value="formatPercent(analytics.metrics.vacancy_rate)" /><p class="mt-1 px-1 text-xs text-slate-500">{{ rateHint(analytics.metrics.known_occupancy_count) }}</p></div>
        <div><PolygonMetricCard label="Filialisierungsgrad" :value="formatPercent(analytics.metrics.chain_store_rate)" /><p class="mt-1 px-1 text-xs text-slate-500">{{ rateHint(analytics.metrics.known_business_structure_count) }}</p></div>
        <div><PolygonMetricCard label="Ø Flächengröße" :value="formatSquareMetres(analytics.metrics.average_area_m2)" /></div>
        <div><PolygonMetricCard label="Median Flächengröße" :value="formatSquareMetres(analytics.metrics.median_area_m2)" /></div>
        <div><PolygonMetricCard label="Orte und Einrichtungen" :value="formatNumber(analytics.poi_count)" /></div>
        <div><PolygonMetricCard label="Verkaufsflächendichte" :value="analytics.retail_area_density_m2_per_km2 == null ? '—' : `${formatNumber(analytics.retail_area_density_m2_per_km2)} m²/km²`" /></div>
        <div><PolygonMetricCard label="Gebietsfläche" :value="`${formatNumber(area.area_m2 / 1_000_000)} km²`" /></div>
      </dl>
    </section>

    <div class="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,.8fr)]">
      <AnalysisAreaDetailMap :area="area" />
      <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="einordnung">
        <h2 id="einordnung" class="text-xl font-black text-slate-950">Einordnung</h2>
        <p class="mt-3 leading-7 text-slate-700">{{ comparisonText }}</p>
        <dl v-if="area.area_type !== 'MUNICIPALITY'" class="mt-5 grid grid-cols-2 gap-3 border-t border-slate-200 pt-5 text-sm">
          <div><dt class="font-semibold text-slate-500">{{ area.name }}</dt><dd class="mt-1 font-black">{{ formatPercent(comparison.area_metrics.vacancy_rate) }}</dd></div>
          <div><dt class="font-semibold text-slate-500">{{ comparison.municipality.name }}</dt><dd class="mt-1 font-black">{{ formatPercent(comparison.municipality_metrics.vacancy_rate) }}</dd></div>
        </dl>
        <dl v-if="area.parent" class="mt-5 border-t border-slate-200 pt-5 text-sm">
          <dt class="font-semibold text-slate-500">Übergeordnetes Gebiet</dt>
          <dd class="mt-1"><NuxtLink class="font-bold text-[#154d73] underline" :to="`/gebiete/${area.parent.slug}`">{{ area.parent.name }}</NuxtLink></dd>
          <template v-if="area.municipality && area.municipality.id !== area.parent.id">
            <dt class="mt-4 font-semibold text-slate-500">Gemeinde</dt>
            <dd class="mt-1"><NuxtLink class="font-bold text-[#154d73] underline" :to="`/gebiete/${area.municipality.slug}`">{{ area.municipality.name }}</NuxtLink></dd>
          </template>
        </dl>
      </section>
    </div>

    <AreaStatistics :statistics="statistics" :series="populationSeries" />

    <div class="mt-8 grid gap-6 lg:grid-cols-2">
      <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="branchen">
        <h2 id="branchen" class="text-xl font-black text-slate-950">Branchenverteilung</h2>
        <p v-if="!analytics.industry_distribution.length" class="mt-4 text-slate-500">Keine Branchendaten verfügbar.</p>
        <ul v-else class="mt-4 space-y-3">
          <li v-for="item in analytics.industry_distribution" :key="item.category" class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-sm" :aria-label="`${getIndustryLabel(item.category)}: ${formatNumber(item.count)} Flächen`">
            <span>{{ getIndustryLabel(item.category) }}</span><strong>{{ formatNumber(item.count) }}</strong>
            <span class="col-span-2 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"><span class="block h-full rounded-full" :style="{ width: `${industryShare(item.count)}%`, backgroundColor: getIndustryColor(item.category) }" /></span>
          </li>
        </ul>
      </section>
      <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="pois">
        <h2 id="pois" class="text-xl font-black text-slate-950">Orte und Einrichtungen im Gebiet</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">In OpenStreetMap erfasste Orte, Einrichtungen und Angebote innerhalb von {{ area.name }}.</p>
        <p v-if="!analytics.poi_categories.length" class="mt-4 text-slate-500">Keine Orte oder Einrichtungen verfügbar.</p>
        <ul v-else class="mt-4 grid grid-cols-2 gap-3">
          <li v-for="item in analytics.poi_categories" :key="item.category">
            <NuxtLink
              class="group flex min-h-28 flex-col rounded-xl border border-slate-200 bg-slate-50 p-3 transition hover:border-[#154d73] hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
              :to="areaPoiMapLink(area.slug, item.category)"
              :aria-label="`${formatNumber(item.count)} ${getPoiCategoryLabel(item.category)} im Gebiet ${area.name} auf der Karte anzeigen`"
            >
              <span class="text-sm font-semibold text-slate-700">{{ getPoiCategoryLabel(item.category) }}</span>
              <strong class="mt-1 text-xl font-black text-slate-950">{{ formatNumber(item.count) }}</strong>
              <span class="mt-auto pt-2 text-xs font-bold text-[#154d73] group-hover:underline">Auf Karte anzeigen <span aria-hidden="true">→</span></span>
            </NuxtLink>
          </li>
        </ul>
      </section>
    </div>

    <section v-if="area.children.length" class="mt-8" aria-labelledby="untergebiete">
      <h2 id="untergebiete" class="text-2xl font-black text-slate-950">Untergeordnete Gebiete</h2>
      <ul class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="child in area.children" :key="child.id"><NuxtLink class="block rounded-2xl border border-slate-200 bg-white p-5 font-bold text-[#154d73] shadow-sm hover:border-[#154d73]" :to="`/gebiete/${child.slug}`">{{ child.name }} <span aria-hidden="true">→</span></NuxtLink></li>
      </ul>
    </section>

    <section v-if="area.external_links.wikipedia || area.external_links.wikidata" class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="externe-quellen">
      <h2 id="externe-quellen" class="text-xl font-black text-slate-950">Externe Quellen</h2>
      <p class="mt-2 text-sm leading-6 text-slate-600">Geprüfte Verknüpfungen zu weiterführenden Informationen über {{ area.name }}.</p>
      <AreaExternalLinks class="mt-4" :area-name="area.name" :links="area.external_links" variant="card" />
    </section>

    <section class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="flaechen">
      <div class="flex flex-wrap items-center justify-between gap-3"><h2 id="flaechen" class="text-2xl font-black text-slate-950">Flächen im Gebiet</h2><NuxtLink class="font-bold text-[#154d73] underline" :to="{ path: '/karte', query: { gebiet: area.slug } }">Alle in der Karte ansehen</NuxtLink></div>
      <p v-if="!polygons.length" class="mt-4 text-slate-500">Für dieses Gebiet sind derzeit keine öffentlichen Flächen erfasst.</p>
      <ul v-else class="mt-4 divide-y divide-slate-200">
        <li v-for="polygon in polygons" :key="polygon.id" class="flex flex-wrap items-center justify-between gap-3 py-4">
          <div><NuxtLink class="font-bold text-slate-950 hover:text-[#154d73] hover:underline" :to="`/flaechen/${polygon.slug}`">{{ polygon.name }}</NuxtLink><p v-if="polygon.address_display_name" class="mt-1 text-sm text-slate-600">{{ polygon.address_display_name }}</p><p class="mt-1 text-sm text-slate-500">{{ getIndustryLabel(polygon.category) }} · {{ formatSquareMetres(polygon.area_m2) }}</p></div>
          <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">{{ occupancyLabel(polygon.occupancy_status) }}</span>
        </li>
      </ul>
    </section>

    <footer class="mt-8 text-sm leading-6 text-slate-500">
      <h2 class="text-lg font-black text-slate-950">Datenquellen und Datenstand</h2>
      <p>Datenstand: {{ formatDate(analytics.metrics.data_updated_at || area.updated_at) }}. Gebietsgrenzen: {{ area.source === 'OSM' ? 'OpenStreetMap' : 'manuell gepflegt' }}<template v-if="area.source_osm_id"> ({{ area.source_osm_type }} {{ area.source_osm_id }})</template>.</p>
      <p class="mt-1">Quoten werden nur aus Flächen mit bekanntem Status berechnet. <NuxtLink class="font-semibold text-[#154d73] underline" to="/dokumentation/methodik">Methodik und Datenquellen</NuxtLink></p>
      <p class="mt-1">Gebiete können mit passenden Einträgen in Wikidata und Wikipedia verknüpft sein. Die Verknüpfungen stammen bevorzugt aus OpenStreetMap und werden automatisch geprüft.</p>
    </footer>
    </template>
  </ContentPageShell>
</template>

<script setup lang="ts">
import {
  areaPoiMapLink,
  getIndustryColor,
  getIndustryLabel,
  getPoiCategoryLabel
} from '#frontend-module-sdk'

const route = useRoute()
const authStore = useAuthStore()
const socialPreview = computed(() => route.query['social-preview'] === '1')
const previewMap = computed(() => route.query.map !== '0')
const previewFacts = computed(() => route.query.facts !== '0')
const previewPois = computed(() => route.query.pois === '1')
const previewBranding = computed(() => route.query.branding !== '0')
const mapReady = ref(false)
const previewReady = computed(() => !previewMap.value || mapReady.value)
const nuxtApp = useNuxtApp()
const slug = Array.isArray(route.params.slug) ? route.params.slug[0] : route.params.slug
if (!slug) throw createError({ statusCode: 404, statusMessage: 'Gebiet nicht gefunden' })
const api = useAnalysisAreaApi()
const { data } = await useAsyncData(`analysis-area-page-${slug}`, async () => {
  try {
    const [area, analytics, comparison, polygons, statistics] = await Promise.all([
      api.bySlug(slug), api.analyticsBySlug(slug), api.comparisonBySlug(slug), api.polygonsBySlug(slug),
      api.statisticsBySlug(slug)
    ])
    const populationSeries = statistics.latest.some(item => item.key === 'population')
      ? await api.statisticSeriesBySlug(slug, 'population')
      : { area: statistics.area, statistics_area: statistics.statistics_area, inherited_from_parent: statistics.inherited_from_parent, source: statistics.source, metric: { key: 'population', name: 'Bevölkerung', unit: 'persons', category: 'Bevölkerung' }, series: [] }
    return { area, analytics, comparison, polygons, statistics, populationSeries }
  } catch (error) {
    const statusCode = typeof error === 'object' && error && 'statusCode' in error ? Number(error.statusCode) : 500
    throw createError({ statusCode: statusCode === 404 ? 404 : 500, statusMessage: statusCode === 404 ? 'Gebiet nicht gefunden' : 'Gebietsdaten konnten nicht geladen werden' })
  }
})
if (!data.value) throw createError({ statusCode: 404, statusMessage: 'Gebiet nicht gefunden' })
const { area, analytics, comparison, polygons, statistics, populationSeries } = data.value
nuxtApp.runWithContext(() => useAnalysisAreaSeo(area))
if (socialPreview.value) useSeoMeta({ robots: 'noindex,nofollow' })
const typeLabel = ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[area.area_type]
const breadcrumbs = [{ label: 'Start', to: '/' }, { label: 'Gebiete', to: '/gebiete' }, ...(area.municipality && area.municipality.id !== area.parent?.id ? [{ label: area.municipality.name, to: `/gebiete/${area.municipality.slug}` }] : []), ...(area.parent ? [{ label: area.parent.name, to: `/gebiete/${area.parent.slug}` }] : []), { label: area.name }]
const numberFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 })
const formatNumber = (value: number) => numberFormat.format(value)
const formatSquareMetres = (value: number | null) => value == null ? '—' : `${numberFormat.format(value)} m²`
const formatPercent = (value: number | null) => value == null ? '—' : `${numberFormat.format(value)} %`
const formatDate = (value: string | null) => value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(new Date(value)) : '—'
const rateHint = (known: number) => known ? `Basis: ${formatNumber(known)} Flächen mit bekanntem Status` : 'Keine belastbare Basis'
const industryTotal = analytics.industry_distribution.reduce((sum, item) => sum + item.count, 0)
const industryShare = (count: number) => industryTotal ? Math.max(2, count / industryTotal * 100) : 0
const occupancyLabel = (status: string) => ({ OCCUPIED: 'Belegt', VACANT: 'Leerstand', UNKNOWN: 'Unbekannt' })[status] || status
const comparisonText = computed(() => {
  if (area.area_type === 'MUNICIPALITY') return `Die Kennzahlen bilden den kommunalen Bezugsrahmen für Vergleiche der untergeordneten Gebiete in ${area.name}.`
  const vacancy = comparison.differences.find(item => item.key === 'vacancy_rate')
  if (vacancy?.difference == null) return `Für einen belastbaren Vergleich mit ${comparison.municipality.name} liegen noch nicht genügend Statusdaten vor.`
  if (vacancy.difference === 0) return `Die berechnete Leerstandsquote entspricht der Quote von ${comparison.municipality.name}.`
  return `Die berechnete Leerstandsquote liegt ${numberFormat.format(Math.abs(vacancy.difference))} Prozentpunkte ${vacancy.difference > 0 ? 'über' : 'unter'} der Quote von ${comparison.municipality.name}.`
})
</script>
