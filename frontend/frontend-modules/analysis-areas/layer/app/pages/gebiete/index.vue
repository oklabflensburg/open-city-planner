<template>
  <ContentPageShell
    title="Gebiete in Flensburg"
    description="Gemeinde, Stadtteile und Quartiere mit Standort-, Einzelhandels- und Statistikdaten im Überblick."
    eyebrow="Gebietsübersicht"
    :breadcrumbs="[{ label: 'Start', to: '/' }, { label: 'Gebiete' }]"
    max-width="wide"
  >
    <div
      data-social-preview-capture
      data-social-preview-ready="true"
      :class="socialPreview ? 'rounded-3xl border border-slate-200 bg-slate-50 p-6' : ''"
    >
      <div v-if="socialPreview" class="mb-6">
        <p class="text-sm font-black uppercase tracking-widest text-[#154d73]">Stadtplaner · OK Lab Flensburg</p>
        <h1 class="mt-2 text-4xl font-black text-slate-950">Gebiete in Flensburg</h1>
        <p class="mt-2 text-slate-600">Gemeinde, Stadtteile und Quartiere im Überblick</p>
      </div>

      <p v-if="!areas?.length" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
        Derzeit sind keine auswertbaren Gebiete veröffentlicht.
      </p>

      <div v-else class="space-y-10">
        <section aria-labelledby="area-overview-heading" class="rounded-2xl border border-slate-200 bg-slate-50 p-5 sm:p-6">
          <h2 id="area-overview-heading" class="text-2xl font-black text-slate-950">Flensburg räumlich verstehen</h2>
          <p class="mt-3 max-w-4xl leading-7 text-slate-700">
            Die Übersicht ordnet {{ totalAreaCount }} veröffentlichte Gebiete in
            {{ municipalityCount }} {{ municipalityCount === 1 ? 'Gemeinde' : 'Gemeinden' }},
            {{ districtCount }} Stadtteile und {{ quarterCount }} Quartiere. Die Kennzahlen werden
            aus dem aktuell veröffentlichten Gebietsbestand berechnet.
          </p>
          <p class="mt-3 max-w-4xl leading-7 text-slate-700">
            Auf den Detailseiten finden Sie Gebietsflächen, Verkaufsflächen, Leerstand, Branchen,
            Orte und Einrichtungen sowie – wo vorhanden – kommunale Bevölkerungs- und Haushaltsdaten.
          </p>
          <dl class="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <dt class="text-sm font-semibold text-slate-600">Gemeinden</dt>
              <dd class="mt-1 text-2xl font-black text-slate-950">{{ municipalityCount }}</dd>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <dt class="text-sm font-semibold text-slate-600">Stadtteile</dt>
              <dd class="mt-1 text-2xl font-black text-slate-950">{{ districtCount }}</dd>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <dt class="text-sm font-semibold text-slate-600">Quartiere</dt>
              <dd class="mt-1 text-2xl font-black text-slate-950">{{ quarterCount }}</dd>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <dt class="text-sm font-semibold text-slate-600">Gebiete gesamt</dt>
              <dd class="mt-1 text-2xl font-black text-slate-950">{{ totalAreaCount }}</dd>
            </div>
          </dl>
          <nav class="mt-5 flex flex-wrap gap-x-5 gap-y-3" aria-label="Direkteinstiege zur Gebietsübersicht">
            <a class="font-bold text-[#154d73] underline" href="#stadtteile">Zu den Stadtteilen</a>
            <NuxtLink class="font-bold text-[#154d73] underline" to="/dokumentation/methodik">Methodik und Datenquellen</NuxtLink>
          </nav>
        </section>

        <span id="stadtteile" class="block scroll-mt-24" aria-hidden="true" />
        <section
          v-for="municipality in municipalities"
          :key="municipality.id"
          :aria-labelledby="`area-${municipality.id}`"
        >
          <div class="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p class="text-sm font-bold uppercase tracking-wide text-[#154d73]">Gemeinde</p>
              <h2 :id="`area-${municipality.id}`" class="mt-1 text-2xl font-black text-slate-950">{{ municipality.name }}</h2>
            </div>
            <NuxtLink class="font-bold text-[#154d73] underline" :to="`/gebiete/${municipality.slug}`">Gemeindedaten ansehen</NuxtLink>
          </div>
          <AreaExternalLinks class="mt-2" :area-name="municipality.name" :links="municipality.external_links" />
          <div class="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="district in childrenOf(municipality.id)"
              :key="district.id"
              class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <p class="text-xs font-bold uppercase tracking-wide text-slate-500">Stadtteil</p>
              <h3 class="mt-2 text-xl font-black text-slate-950">
                <NuxtLink class="hover:text-[#154d73] hover:underline" :to="`/gebiete/${district.slug}`">{{ district.name }}</NuxtLink>
              </h3>
              <p class="mt-2 text-sm text-slate-600">
                {{ formatArea(district.area_m2) }} · {{ district.child_count }}
                {{ district.child_count === 1 ? 'Quartier' : 'Quartiere' }}
              </p>
              <AreaExternalLinks class="mt-2" :area-name="district.name" :links="district.external_links" />
              <ul v-if="childrenOf(district.id).length" class="mt-4 flex flex-wrap gap-2" :aria-label="`Quartiere in ${district.name}`">
                <li v-for="quarter in childrenOf(district.id)" :key="quarter.id">
                  <NuxtLink
                    class="inline-flex min-h-11 items-center rounded-full bg-slate-100 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-200"
                    :to="`/gebiete/${quarter.slug}`"
                  >{{ quarter.name }}</NuxtLink>
                </li>
              </ul>
            </article>
          </div>
        </section>
      </div>
    </div>

    <section class="mt-14 border-t border-slate-200 pt-10" aria-labelledby="area-faq-heading">
      <div class="max-w-3xl">
        <p class="text-sm font-bold uppercase tracking-wide text-[#154d73]">Orientierung und Datenquellen</p>
        <h2 id="area-faq-heading" class="mt-2 text-3xl font-black text-slate-950">Häufige Fragen zu Flensburgs Stadtteilen und Quartieren</h2>
      </div>
      <div class="mt-7 grid gap-5 lg:grid-cols-2">
        <article
          v-for="faq in faqItems"
          :key="faq.id"
          class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"
          :class="faq.id === 'district-list' ? 'lg:col-span-2' : ''"
        >
          <h3 class="text-xl font-black text-slate-950">{{ faq.question }}</h3>
          <p class="mt-3 leading-7 text-slate-700">{{ faq.answer }}</p>

          <ul v-if="faq.id === 'district-list'" class="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Alphabetische Liste der Stadtteile">
            <li v-for="district in districts" :key="district.id">
              <NuxtLink class="inline-flex min-h-11 items-center font-bold text-[#154d73] underline" :to="`/gebiete/${district.slug}`">{{ district.name }}</NuxtLink>
            </li>
          </ul>

          <p v-if="faq.id === 'area-data'" class="mt-3">
            <NuxtLink class="font-bold text-[#154d73] underline" to="/dokumentation/methodik">Berechnung und Datenqualität nachlesen</NuxtLink>
          </p>
          <p v-else-if="faq.id === 'boundaries'" class="mt-3">
            <NuxtLink class="font-bold text-[#154d73] underline" to="/dokumentation/methodik#raeumliche-zuordnung">Methodik der Gebietszuordnung</NuxtLink>
          </p>
          <p v-else-if="faq.id === 'statistics-source' || faq.id === 'quarter-statistics'" class="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            <NuxtLink class="font-bold text-[#154d73] underline" to="/dokumentation/statistik">Kommunale Statistik verstehen</NuxtLink>
            <NuxtLink class="font-bold text-[#154d73] underline" to="/dokumentation/methodik">Methodik ansehen</NuxtLink>
          </p>
          <p v-else-if="faq.id === 'map'" class="mt-3">
            <NuxtLink class="font-bold text-[#154d73] underline" to="/karte">GIS-Karte öffnen</NuxtLink>
          </p>
        </article>
      </div>
    </section>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { countAnalysisAreasByType, sortAnalysisAreasByName } from '../../utils/analysisAreaOverview'
import {
  buildAbsoluteUrl,
  buildBreadcrumbStructuredData,
  buildCollectionPageStructuredData,
  buildFaqStructuredData,
  buildItemListStructuredData,
  buildSeoImageUrl,
  serializeStructuredData,
  toMetaDescription
} from '#frontend-module-sdk'

type AreaFaqItem = {
  id: string
  question: string
  answer: string
}

const config = useRuntimeConfig()
const route = useRoute()
const socialPreview = computed(() => route.query['social-preview'] === '1')
const areaApi = useAnalysisAreaApi()
const { data: areas } = await useAsyncData('analysis-area-index', () => areaApi.list())
const publishedAreas = computed(() => areas.value || [])
const municipalities = computed(() => sortAnalysisAreasByName(
  publishedAreas.value.filter(area => area.area_type === 'MUNICIPALITY')
))
const districts = computed(() => sortAnalysisAreasByName(
  publishedAreas.value.filter(area => area.area_type === 'DISTRICT')
))
const municipalityCount = computed(() => countAnalysisAreasByType(publishedAreas.value, 'MUNICIPALITY'))
const districtCount = computed(() => countAnalysisAreasByType(publishedAreas.value, 'DISTRICT'))
const quarterCount = computed(() => countAnalysisAreasByType(publishedAreas.value, 'QUARTER'))
const totalAreaCount = computed(() => publishedAreas.value.length)
const childrenOf = (parentId: string) => sortAnalysisAreasByName(
  publishedAreas.value.filter(area => area.parent_id === parentId)
)
const formatArea = (value: number) => `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(value / 1_000_000)} km²`

const faqItems = computed<AreaFaqItem[]>(() => [
  ...(publishedAreas.value.length
    ? [
        {
          id: 'district-count',
          question: 'Wie viele Stadtteile hat Flensburg?',
          answer: `Im aktuell veröffentlichten Gebietsbestand sind ${districtCount.value} Stadtteile der Gemeinde Flensburg zugeordnet.`
        },
        {
          id: 'quarter-count',
          question: 'Wie viele Quartiere hat Flensburg?',
          answer: `Der Stadtplaner weist aktuell ${quarterCount.value} veröffentlichte Quartiere aus. Sie sind jeweils einem Stadtteil zugeordnet.`
        },
        {
          id: 'district-list',
          question: 'Welche Stadtteile gehören zu Flensburg?',
          answer: `Die veröffentlichten Stadtteile sind ${districts.value.map(area => area.name).join(', ')}. Die alphabetische Liste führt direkt zu den jeweiligen Standortprofilen.`
        }
      ]
    : []),
  {
    id: 'hierarchy',
    question: 'Was ist der Unterschied zwischen Stadtteil und Quartier?',
    answer: 'Der Stadtplaner verwendet die Hierarchie Gemeinde, Stadtteil und Quartier. Stadtteile gliedern die Gemeinde; Quartiere bilden die kleinräumigere Ebene innerhalb eines Stadtteils.'
  },
  {
    id: 'area-data',
    question: 'Welche Daten zeigt der Stadtplaner für Stadtteile und Quartiere?',
    answer: 'Die Gebietsseiten zeigen unter anderem Gebietsfläche, Verkaufsflächen, Leerstand, Branchen, Orte und Einrichtungen sowie verfügbare Vergleichs- und Statistikwerte.'
  },
  {
    id: 'boundaries',
    question: 'Woher stammen die Gebietsgrenzen?',
    answer: 'Die Analysegebietsgrenzen werden überwiegend aus OpenStreetMap synchronisiert. Die jeweilige Detailseite nennt Quelle und Datenstand; einzelne Gebiete können manuell gepflegt sein.'
  },
  {
    id: 'statistics-source',
    question: 'Woher stammen Bevölkerungs- und Haushaltsdaten?',
    answer: 'Der Stadtplaner importiert veröffentlichte Bevölkerungs- und Haushaltsdaten aus dem Zahlenspiegel der Stadt Flensburg und speichert sie mit Quelle und Berichtsperiode.'
  },
  {
    id: 'quarter-statistics',
    question: 'Gibt es für jedes Quartier eigene Statistikwerte?',
    answer: 'Nein. Quartiere erhalten keine künstlich aufgeteilten Stadtteilwerte. Wenn ein veröffentlichter Wert des übergeordneten Stadtteils angezeigt wird, kennzeichnet der Stadtplaner das tatsächlich verwendete Statistikgebiet.'
  },
  {
    id: 'map',
    question: 'Kann ich ein Gebiet direkt auf der Karte öffnen?',
    answer: 'Ja. Jede Gebietsdetailseite enthält einen Link zur GIS-Karte, der das Gebiet auswählt und den Kartenausschnitt darauf ausrichtet.'
  }
])

const title = 'Gebiete in Flensburg – Standortdaten | Stadtplaner'
const description = toMetaDescription('', 'Gemeinde, Stadtteile und Quartiere in Flensburg: Verkaufsflächen, Leerstand, Branchen, POIs und kommunale Statistik im Überblick.')
const canonical = buildAbsoluteUrl(config.public.siteUrl, '/gebiete')
const image = buildSeoImageUrl(config.public.siteUrl, config.public.defaultOgImage)
const structuredData = computed(() => [
  buildBreadcrumbStructuredData(config.public.siteUrl, [
    { name: 'Start', path: '/' },
    { name: 'Gebiete', path: '/gebiete' }
  ]),
  buildCollectionPageStructuredData(config.public.siteUrl, '/gebiete', 'Gebiete in Flensburg', description),
  ...(publishedAreas.value.length
    ? [buildItemListStructuredData(
        config.public.siteUrl,
        'Stadtteile in Flensburg',
        districts.value.map(area => ({ name: area.name, path: `/gebiete/${area.slug}` }))
      )]
    : []),
  buildFaqStructuredData(faqItems.value.map(item => ({
    question: item.question,
    answer: item.answer
  })))
])

useSeoMeta({
  title,
  description,
  robots: socialPreview.value ? 'noindex,nofollow' : 'index,follow',
  ogTitle: title,
  ogDescription: description,
  ogUrl: canonical,
  ogType: 'website',
  ogSiteName: config.public.siteName,
  ogLocale: config.public.siteLocale,
  ogImage: image || undefined,
  ogImageAlt: image ? 'Stadtplaner des OK Lab Flensburg' : undefined,
  ogImageWidth: image ? 1200 : undefined,
  ogImageHeight: image ? 630 : undefined,
  twitterCard: image ? 'summary_large_image' : 'summary',
  twitterTitle: title,
  twitterDescription: description,
  twitterImage: image || undefined,
  twitterImageAlt: image ? 'Stadtplaner des OK Lab Flensburg' : undefined
})
useHead(() => ({
  link: [{ rel: 'canonical', href: canonical }],
  script: [{ type: 'application/ld+json', innerHTML: serializeStructuredData(structuredData.value) }]
}))
</script>
