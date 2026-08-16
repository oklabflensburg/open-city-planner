<template>
  <ContentPageShell
    title="Gebiete in Flensburg"
    description="Gemeinde, Stadtteile und Quartiere mit eigenen Standort- und Einzelhandelsdaten."
    eyebrow="Gebietsübersicht"
    :breadcrumbs="[{ label: 'Start', to: '/' }, { label: 'Gebiete' }]"
    max-width="wide"
  >
    <p v-if="!areas?.length" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
      Derzeit sind keine auswertbaren Gebiete veröffentlicht.
    </p>
    <div v-else class="space-y-10">
      <section v-for="municipality in municipalities" :key="municipality.id" :aria-labelledby="`area-${municipality.id}`">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p class="text-sm font-bold uppercase tracking-wide text-[#154d73]">Gemeinde</p>
            <h2 :id="`area-${municipality.id}`" class="mt-1 text-2xl font-black text-slate-950">{{ municipality.name }}</h2>
          </div>
          <NuxtLink class="font-bold text-[#154d73] underline" :to="`/gebiete/${municipality.slug}`">Gemeindedaten ansehen</NuxtLink>
        </div>
        <div class="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          <article v-for="district in childrenOf(municipality.id)" :key="district.id" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-500">Stadtteil</p>
            <h3 class="mt-2 text-xl font-black text-slate-950">
              <NuxtLink class="hover:text-[#154d73] hover:underline" :to="`/gebiete/${district.slug}`">{{ district.name }}</NuxtLink>
            </h3>
            <p class="mt-2 text-sm text-slate-600">{{ formatArea(district.area_m2) }} · {{ district.child_count }} {{ district.child_count === 1 ? 'Quartier' : 'Quartiere' }}</p>
            <ul v-if="childrenOf(district.id).length" class="mt-4 flex flex-wrap gap-2" aria-label="Quartiere">
              <li v-for="quarter in childrenOf(district.id)" :key="quarter.id">
                <NuxtLink class="inline-flex min-h-9 items-center rounded-full bg-slate-100 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-200" :to="`/gebiete/${quarter.slug}`">{{ quarter.name }}</NuxtLink>
              </li>
            </ul>
          </article>
        </div>
      </section>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { AnalysisArea } from '~/types/analysisArea'
import { buildAbsoluteUrl, buildBreadcrumbStructuredData, serializeStructuredData, toMetaDescription } from '~/utils/seo'

const config = useRuntimeConfig()
const areaApi = useAnalysisAreaApi()
const { data: areas } = await useAsyncData('analysis-area-index', () => areaApi.list())
const municipalities = computed(() => (areas.value || []).filter(area => area.area_type === 'MUNICIPALITY'))
const childrenOf = (parentId: string) => (areas.value || []).filter(area => area.parent_id === parentId)
const formatArea = (value: number) => `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(value / 1_000_000)} km²`
const title = 'Gebiete in Flensburg – Standortdaten | Stadtplanner'
const description = toMetaDescription('', 'Gemeinde, Stadtteile und Quartiere in Flensburg: Verkaufsflächen, Leerstand, Branchen, POIs und belastbare Standortdaten im Überblick.')
const canonical = buildAbsoluteUrl(config.public.siteUrl, '/gebiete')

useSeoMeta({ title, description, robots: 'index,follow', ogTitle: title, ogDescription: description, ogUrl: canonical, ogType: 'website', twitterCard: 'summary' })
useHead({
  link: [{ rel: 'canonical', href: canonical }],
  script: [{ type: 'application/ld+json', innerHTML: serializeStructuredData(buildBreadcrumbStructuredData(config.public.siteUrl, [{ name: 'Start', path: '/' }, { name: 'Gebiete', path: '/gebiete' }])) }]
})
</script>
