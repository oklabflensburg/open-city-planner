<template>
  <div class="bg-[#f4f7f7]">
    <section class="border-b border-slate-200 bg-white">
      <div class="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[minmax(0,1fr)_22rem] lg:px-8">
        <div>
          <p class="text-sm font-bold uppercase tracking-[0.14em] text-[#086b78]">Offene Stadtentwicklung in Flensburg</p>
          <h1 class="mt-3 max-w-4xl text-4xl font-black tracking-tight text-slate-950 sm:text-5xl">{{ analysisAreasEnabled ? 'Flächen und Stadtgebiete auf einen Blick' : 'Öffentliche Flächen auf einen Blick' }}</h1>
          <p class="mt-5 max-w-3xl text-lg leading-8 text-slate-600">{{ analysisAreasEnabled ? 'Der Stadtplaner macht öffentliche Verkaufsflächen, Stadtteile und statistische Bezirke direkt auffindbar.' : 'Der Stadtplaner macht öffentliche Verkaufsflächen direkt auffindbar.' }} Alle Einträge dieser Seite werden serverseitig ausgegeben und sind ohne Kartenanwendung zugänglich.</p>
          <div class="mt-7 flex flex-wrap gap-3">
            <NuxtLink class="inline-flex min-h-11 items-center rounded-xl bg-[#154d73] px-5 font-bold text-white hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/karte">Interaktive Karte öffnen</NuxtLink>
            <NuxtLink v-if="analysisAreasEnabled" class="inline-flex min-h-11 items-center rounded-xl border border-slate-300 bg-white px-5 font-bold text-slate-800 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/gebiete">Gebiete entdecken</NuxtLink>
            <NuxtLink class="inline-flex min-h-11 items-center px-2 font-bold text-[#154d73] underline-offset-4 hover:underline" to="/open-data">Open Data ansehen</NuxtLink>
          </div>
        </div>
        <dl class="grid grid-cols-2 gap-3 self-end">
          <div class="rounded-2xl bg-[#edf4f8] p-5"><dt class="text-sm text-slate-600">Flächen</dt><dd class="mt-1 text-3xl font-black text-[#154d73]">{{ polygons.length }}</dd></div>
          <div v-if="analysisAreasEnabled" class="rounded-2xl bg-[#edf4f8] p-5"><dt class="text-sm text-slate-600">Gebiete</dt><dd class="mt-1 text-3xl font-black text-[#154d73]">{{ publicAreas.length }}</dd></div>
        </dl>
      </div>
    </section>

    <main class="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section
        v-if="showSignupCta"
        data-home-signup-cta
        class="mb-12 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        aria-labelledby="signup-heading"
      >
        <div class="grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.75fr)] lg:items-center">
          <div>
            <p class="text-sm font-bold text-[#086b78]">Mit einem kostenlosen Konto</p>
            <h2 id="signup-heading" class="mt-1 text-3xl font-black text-slate-950">Eigene Flächen dauerhaft verwalten</h2>
            <p class="mt-3 max-w-2xl leading-7 text-slate-600">Mit einem kostenlosen Konto können Sie eigene Flächen anlegen, später wiederfinden und Ihre Arbeit im Stadtplaner fortführen.</p>
            <div class="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <NuxtLink class="page-button-primary w-full sm:w-auto" to="/registrieren">Kostenlos registrieren</NuxtLink>
              <NuxtLink class="page-button-secondary w-full sm:w-auto" to="/login">Anmelden</NuxtLink>
            </div>
          </div>
          <ul class="grid gap-3" aria-label="Vorteile eines Kontos">
            <li v-for="benefit in accountBenefits" :key="benefit" class="flex min-h-12 items-center gap-3 rounded-xl bg-[#edf4f8] px-4 py-3 font-semibold text-slate-800">
              <Check class="size-5 shrink-0 text-[#086b78]" aria-hidden="true" />
              <span>{{ benefit }}</span>
            </li>
          </ul>
        </div>
      </section>

      <div v-if="error" class="rounded-xl border border-rose-200 bg-white p-5 text-rose-800" role="alert">Das öffentliche Verzeichnis konnte nicht geladen werden. Bitte versuchen Sie es später erneut.</div>
      <template v-else>
        <nav v-if="polygonGroups.length" class="mb-12 rounded-2xl border border-slate-200 bg-white p-5" aria-label="Branchenübersicht">
          <h2 class="text-lg font-black text-slate-950">Branchenübersicht</h2>
          <ul class="mt-4 flex flex-wrap gap-2">
            <li v-for="group in polygonGroups" :key="group.key">
              <a class="inline-flex min-h-11 items-center gap-2 rounded-full border border-slate-200 px-4 text-sm font-bold text-slate-700 hover:border-[#154d73] hover:text-[#154d73]" :href="`#industry-${group.key}`">
                <span class="size-2.5 rounded-full" :style="{ backgroundColor: group.color }" aria-hidden="true" />{{ group.label }} · {{ group.items.length }}
              </a>
            </li>
          </ul>
        </nav>

        <section v-if="analysisAreasEnabled" aria-labelledby="areas-heading">
          <div class="flex flex-wrap items-end justify-between gap-3">
            <div><p class="text-sm font-bold text-[#086b78]">Räumliche Gliederung</p><h2 id="areas-heading" class="mt-1 text-3xl font-black text-slate-950">Stadtteile und Quartiere</h2></div>
            <NuxtLink class="font-bold text-[#154d73] underline-offset-4 hover:underline" to="/gebiete">Alle Gebietsdetails</NuxtLink>
          </div>
          <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <article v-for="area in publicAreas" :key="area.id" class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <img class="aspect-video w-full bg-slate-100 object-cover" :src="areaPreviewUrl(area.slug)" :srcset="areaPreviewSrcset(area.slug)" sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw" :alt="`Kartendarstellung des Gebiets ${area.name} in Flensburg`" width="640" height="360" loading="lazy" decoding="async">
              <div class="p-4">
                <p class="text-xs font-bold uppercase tracking-wide text-slate-500">{{ areaTypeLabel(area.area_type) }}</p>
                <h3 class="mt-1 text-lg font-black text-slate-950"><NuxtLink class="hover:text-[#154d73]" :to="`/gebiete/${area.slug}`">{{ area.name }}</NuxtLink></h3>
                <p class="mt-2 text-sm text-slate-600">{{ formatArea(area.area_m2) }}<template v-if="area.child_count"> · {{ area.child_count }} untergeordnete Gebiete</template></p>
                <NuxtLink class="mt-3 inline-flex min-h-10 items-center font-bold text-[#154d73]" :to="{ path: '/karte', query: { gebiet: area.slug } }">Auf der Karte anzeigen</NuxtLink>
              </div>
            </article>
          </div>
        </section>

        <section class="mt-14" aria-labelledby="polygons-heading">
          <p class="text-sm font-bold text-[#086b78]">Öffentliches Flächenverzeichnis</p>
          <h2 id="polygons-heading" class="mt-1 text-3xl font-black text-slate-950">Flächen nach Branche</h2>
          <p class="mt-3 max-w-3xl text-slate-600">{{ polygons.length }} öffentliche Flächen, vollständig und nach der bestehenden Branchentaxonomie gruppiert.</p>
          <div class="mt-8 space-y-10">
            <section v-for="group in polygonGroups" :key="group.key" :aria-labelledby="`industry-${group.key}`">
              <div class="flex items-center gap-3">
                <span class="size-3 rounded-full" :style="{ backgroundColor: group.color }" aria-hidden="true" />
                <h3 :id="`industry-${group.key}`" class="text-xl font-black text-slate-950">{{ group.label }}</h3>
                <span class="text-sm text-slate-500">{{ group.items.length }}</span>
              </div>
              <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                <article v-for="polygon in group.items" :key="polygon.slug" class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <img class="aspect-video w-full bg-slate-100 object-cover" :src="polygonPreviewUrl(polygon.slug)" :srcset="polygonPreviewSrcset(polygon.slug)" sizes="(min-width: 1280px) 25vw, (min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw" :alt="`Kartendarstellung der Fläche ${polygon.name}`" width="640" height="360" loading="lazy" decoding="async">
                  <div class="p-4">
                    <h4 class="font-black leading-snug text-slate-950"><NuxtLink class="hover:text-[#154d73]" :to="`/flaechen/${polygon.slug}`">{{ polygon.name }}</NuxtLink></h4>
                    <p v-if="polygon.address_display_name" class="mt-2 line-clamp-2 text-sm text-slate-600">{{ polygon.address_display_name }}</p>
                    <p v-if="polygon.quarter_name || polygon.district_name" class="mt-2 text-xs font-semibold text-slate-500">{{ polygon.quarter_name || polygon.district_name }}</p>
                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                      <span class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">{{ occupancyLabel(polygon.occupancy_status) }}</span>
                      <span v-if="polygon.floor" class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">Etage {{ polygon.floor }}</span>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-x-4"><NuxtLink class="inline-flex min-h-10 items-center font-bold text-[#154d73]" :to="`/flaechen/${polygon.slug}`">Details ansehen</NuxtLink><NuxtLink class="inline-flex min-h-10 items-center font-bold text-[#154d73]" :to="{ path: '/karte', query: { flaeche: polygon.slug } }">Auf der Karte anzeigen</NuxtLink></div>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="mt-16" aria-labelledby="topics-heading">
          <h2 id="topics-heading" class="text-3xl font-black text-slate-950">Stadtentwicklung mit offenen Daten erkunden</h2>
          <div class="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <article v-for="topic in topics" :key="topic.title" class="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 class="text-lg font-black text-slate-950">{{ topic.title }}</h3><p class="mt-2 leading-7 text-slate-600">{{ topic.text }}</p><NuxtLink class="mt-3 inline-flex min-h-10 items-center font-bold text-[#154d73] underline-offset-4 hover:underline" :to="topic.to">{{ topic.link }}</NuxtLink>
            </article>
          </div>
        </section>

        <section class="mt-14 rounded-2xl border border-slate-200 bg-white p-6" aria-labelledby="questions-heading">
          <h2 id="questions-heading" class="text-2xl font-black text-slate-950">Häufige Fragen zum Stadtplaner</h2>
          <dl class="mt-5 grid gap-x-8 gap-y-6 md:grid-cols-2">
            <div v-for="item in questions" :key="item.question"><dt class="font-black text-slate-900">{{ item.question }}</dt><dd class="mt-2 leading-7 text-slate-600">{{ item.answer }}</dd></div>
          </dl>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { Check } from '@lucide/vue'
import type { PublicAreaReference, PublicAreaType } from '~/types/publicAreaReference'
import type { OccupancyStatus, PolygonDirectoryItem } from '~/types/geo'
import { buildApiUrl } from '~/utils/apiUrl'
import { buildAbsoluteUrl } from '~/utils/seo'
import { getIndustryColor, getIndustryLabel, industries } from '~/utils/industries'

const config = useRuntimeConfig()
const enabledFrontendModules = new Set((config.public.frontendModules ?? []) as readonly string[])
const analysisAreasEnabled = enabledFrontendModules.has('analysis-areas')
const authStore = useAuthStore()
const mounted = ref(false)
const showSignupCta = computed(() => !mounted.value || !authStore.authenticated)
onMounted(() => { mounted.value = true })
const { data, error } = await useAsyncData('public-home-directory', async () => {
  const [polygons, areas] = await Promise.all([
    usePolygonApi().directoryAll(),
    analysisAreasEnabled
      ? useApi().request<PublicAreaReference[]>('/analysis-areas')
      : Promise.resolve([] as PublicAreaReference[])
  ])
  return { polygons, areas }
})
const polygons = computed(() => data.value?.polygons || [] as PolygonDirectoryItem[])
const areas = computed(() => data.value?.areas || [] as PublicAreaReference[])
const publicAreas = computed(() => areas.value.filter(area => area.area_type === 'DISTRICT' || area.area_type === 'QUARTER'))
const polygonGroups = computed(() => {
  const order = new Map<string, number>(industries.map((industry, index) => [industry.key, index]))
  const grouped = new Map<string, PolygonDirectoryItem[]>()
  for (const polygon of polygons.value) grouped.set(polygon.category, [...(grouped.get(polygon.category) || []), polygon])
  return [...grouped.entries()]
    .sort(([left], [right]) => (order.get(left) ?? 999) - (order.get(right) ?? 999) || left.localeCompare(right, 'de'))
    .map(([key, items]) => ({ key, items, label: getIndustryLabel(key), color: getIndustryColor(key) }))
})

const previewUrl = (path: string) => buildApiUrl(config.public.apiBaseUrl, `${path}?width=640&height=360`)
const polygonPreviewUrl = (slug: string) => previewUrl(`/polygons/by-slug/${encodeURIComponent(slug)}/preview.webp`)
const areaPreviewUrl = (slug: string) => previewUrl(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/preview.webp`)
const previewSrcset = (path: string) => `${buildApiUrl(config.public.apiBaseUrl, `${path}?width=320&height=180`)} 320w, ${buildApiUrl(config.public.apiBaseUrl, `${path}?width=640&height=360`)} 640w`
const polygonPreviewSrcset = (slug: string) => previewSrcset(`/polygons/by-slug/${encodeURIComponent(slug)}/preview.webp`)
const areaPreviewSrcset = (slug: string) => previewSrcset(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/preview.webp`)
const areaTypeLabel = (type: PublicAreaType) => ({ MUNICIPALITY: 'Stadt', DISTRICT: 'Stadtteil', QUARTER: 'Statistischer Bezirk' })[type]
const occupancyLabel = (status: OccupancyStatus) => ({ OCCUPIED: 'Belegt', VACANT: 'Leerstehend', UNKNOWN: 'Status unbekannt' })[status]
const formatArea = (area: number) => `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(area / 1_000_000)} km²`
const accountBenefits = [
  'Eigene Flächen anlegen und speichern',
  'Gespeicherte Flächen wieder aufrufen',
  'Eigene Einträge verwalten und weiterbearbeiten'
]
const topics = [
  { title: 'Flächen und Leerstände', text: 'Öffentliche Verkaufsflächen nach Status, Branche und Lage finden und ihre Detaildaten nachvollziehen.', to: '/karte', link: 'Flächen auf der Karte erkunden' },
  { title: 'Gebiete vergleichen', text: 'Stadtteile und Quartiere anhand vorhandener Flächen-, Branchen- und Statistikdaten einordnen.', to: '/vergleich', link: 'Zum Gebietsvergleich' },
  { title: 'Open Data und Datenquellen', text: 'Herkunft, Lizenz, Aktualität und technische Bereitstellung der verwendeten Daten nachvollziehen.', to: '/open-data', link: 'Open Data ansehen' },
  { title: 'Wie entstehen die Daten?', text: 'Methodik, räumliche Zuordnung und Grenzen der berechneten Kennzahlen transparent nachlesen.', to: '/dokumentation/methodik', link: 'Methodik lesen' },
  ...(analysisAreasEnabled
    ? [{ title: 'Stadtteile und Quartiere', text: 'Die räumliche Hierarchie Flensburgs über dauerhafte, öffentlich verlinkbare Gebietsprofile erschließen.', to: '/gebiete', link: 'Gebiete entdecken' }]
    : []),
  { title: 'Über das Projekt', text: 'Mehr über die Civic-Tech-Plattform und das OK Lab Flensburg erfahren.', to: '/ueber-das-projekt', link: 'Projekt kennenlernen' }
]
const questions = [
  { question: 'Was kann ich mit dem Stadtplaner tun?', answer: 'Sie können Flächen und Gebiete finden, auf der Karte untersuchen und vorhandene Kennzahlen vergleichen.' },
  { question: 'Welche Flächen sind erfasst?', answer: 'Das Verzeichnis zeigt alle derzeit öffentlich geführten Stadtplaner-Flächen. Fehlende Werte werden nicht geschätzt.' },
  { question: 'Wie finde ich Leerstände?', answer: 'In der interaktiven Karte lässt sich der öffentliche Belegungsstatus filtern; unbekannte Status bleiben als unbekannt gekennzeichnet.' },
  { question: 'Woher stammen die Daten?', answer: 'Die Plattform verbindet gepflegte Stadtplaner-Daten, OpenStreetMap und veröffentlichte kommunale Statistik. Detailseiten nennen Quelle und Datenstand.' }
]

const description = analysisAreasEnabled
  ? 'Öffentliches Verzeichnis der Verkaufsflächen, Stadtteile und statistischen Bezirke in Flensburg.'
  : 'Öffentliches Verzeichnis der Verkaufsflächen in Flensburg.'
const structuredData = [
  { '@context': 'https://schema.org', '@type': 'WebSite', '@id': `${buildAbsoluteUrl(config.public.siteUrl, '/')}#website`, name: config.public.siteName, url: buildAbsoluteUrl(config.public.siteUrl, '/'), description },
  { '@context': 'https://schema.org', '@type': 'CollectionPage', name: analysisAreasEnabled ? 'Flächen und Stadtgebiete in Flensburg' : 'Öffentliche Flächen in Flensburg', url: buildAbsoluteUrl(config.public.siteUrl, '/'), description },
  ...(analysisAreasEnabled
    ? [{ '@context': 'https://schema.org', '@type': 'ItemList', name: 'Stadtteile und Quartiere in Flensburg', numberOfItems: publicAreas.value.length, itemListElement: publicAreas.value.map((area, index) => ({ '@type': 'ListItem', position: index + 1, name: area.name, url: buildAbsoluteUrl(config.public.siteUrl, `/gebiete/${area.slug}`) })) }]
    : [])
]
usePageSeo({
  title: analysisAreasEnabled ? 'Flächen und Stadtgebiete in Flensburg' : 'Öffentliche Flächen in Flensburg',
  description,
  path: '/',
  structuredData
})
</script>
