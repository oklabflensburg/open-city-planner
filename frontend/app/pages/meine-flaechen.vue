<template>
  <ContentPageShell
    title="Meine Flächen"
    description="Verwalten Sie Ihre angelegten Flächen, durchsuchen Sie Einträge nach Name oder Kategorie und öffnen Sie die Detailansicht zur weiteren Bearbeitung."
    eyebrow="Flächenverwaltung"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Meine Flächen' }]"
    max-width="content"
  >
    <template #actions>
      <div class="flex min-w-0 items-center gap-3 rounded-md border border-[#dfe4e6] bg-white px-3 py-2">
        <UserAvatar :user="authStore.user" size="sm" />
        <div class="min-w-0">
          <p class="truncate text-sm font-bold text-[#202427]">{{ authStore.displayName }}</p>
          <p class="truncate text-xs text-[#687176]">Eigene Einträge</p>
        </div>
      </div>
    </template>

    <div v-if="loading" class="space-y-5" aria-live="polite" aria-label="Flächen werden geladen">
      <div class="grid gap-3 sm:grid-cols-3">
        <div v-for="item in 3" :key="item" class="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" />
      </div>
      <Card class="space-y-3 p-6">
        <div class="h-11 animate-pulse rounded-xl bg-slate-100" />
        <div v-for="item in 5" :key="item" class="h-12 animate-pulse rounded-xl bg-slate-100" />
      </Card>
    </div>

    <Card v-else-if="error" class="border-rose-200 p-8 text-center">
      <p class="font-semibold text-slate-950">Flächen konnten nicht geladen werden.</p>
      <p class="mt-2 text-sm text-slate-600">Bitte versuchen Sie es erneut.</p>
      <button class="page-button-secondary mt-4" type="button" @click="loadPolygons">Erneut versuchen</button>
    </Card>

    <Card v-else-if="!polygons.length" class="p-8 text-center sm:p-10">
      <h2 class="text-lg font-bold text-slate-950">Noch keine eigenen Flächen</h2>
      <p class="mt-2 text-sm leading-6 text-slate-600">Auf der Karte finden Sie den Einstieg zum Anlegen Ihrer ersten Fläche.</p>
      <NuxtLink class="page-button-primary mt-5" to="/">Zur Karte</NuxtLink>
    </Card>

    <template v-else>
      <section class="grid gap-3 sm:grid-cols-3" aria-label="Übersicht Ihrer Flächen">
        <Card class="p-4 sm:p-5">
          <p class="text-sm font-semibold text-slate-600">Eigene Flächen</p>
          <p class="mt-1 text-2xl font-black text-slate-950">{{ polygons.length }}</p>
        </Card>
        <Card class="p-4 sm:p-5">
          <p class="text-sm font-semibold text-slate-600">Kategorien</p>
          <p class="mt-1 text-2xl font-black text-slate-950">{{ categoryCount }}</p>
        </Card>
        <Card class="p-4 sm:p-5">
          <p class="text-sm font-semibold text-slate-600">Zuletzt geändert</p>
          <p class="mt-1 text-2xl font-black text-slate-950">{{ latestUpdatedDate }}</p>
        </Card>
      </section>

      <Card class="mt-5 overflow-hidden">
        <div class="border-b border-slate-200 p-4 sm:p-5">
          <div class="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(12rem,0.45fr)_minmax(12rem,0.45fr)] md:items-end">
            <label class="min-w-0">
              <span class="field-label">Flächen durchsuchen</span>
              <span class="relative block">
                <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                <input
                  v-model="searchQuery"
                  class="field-input pl-10 pr-11"
                  type="search"
                  placeholder="Nach Name, Kategorie oder Ort suchen …"
                  autocomplete="off"
                >
                <button
                  v-if="searchQuery"
                  class="absolute right-1 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#154d73]"
                  type="button"
                  aria-label="Suche zurücksetzen"
                  @click="searchQuery = ''"
                >
                  <X class="size-4" aria-hidden="true" />
                </button>
              </span>
            </label>

            <label class="min-w-0">
              <span class="field-label">Kategorie</span>
              <select v-model="selectedCategory" class="field-input">
                <option value="">Alle Kategorien</option>
                <option v-for="option in categoryOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>

            <label class="min-w-0">
              <span class="field-label">Sortieren</span>
              <select v-model="sortBy" class="field-input">
                <option v-for="option in polygonSortOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>
          </div>

          <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p class="text-sm font-bold text-slate-800" aria-live="polite" aria-atomic="true">{{ resultLabel }}</p>
            <button v-if="hasActiveFilters" class="text-sm font-bold text-[#154d73] hover:underline" type="button" @click="resetFilters">
              Suche und Filter zurücksetzen
            </button>
          </div>
        </div>

        <div v-if="!visiblePolygons.length" class="px-6 py-12 text-center sm:px-10">
          <h2 class="text-lg font-bold text-slate-950">Keine Flächen gefunden</h2>
          <p class="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">{{ noResultsDescription }}</p>
          <button class="page-button-secondary mt-5" type="button" @click="resetFilters">Suche zurücksetzen</button>
        </div>

        <template v-else>
          <div class="grid gap-3 p-4 md:hidden">
            <article v-for="polygon in visiblePolygons" :key="polygon.id" class="rounded-xl border border-slate-200 bg-white p-4">
              <h2 class="text-base font-bold text-slate-950">{{ polygon.name }}</h2>
              <PolygonCategoryBadge class="mt-2" :category="polygon.category" />
              <dl class="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm">
                <div>
                  <dt class="text-slate-500">Erstellt am</dt>
                  <dd class="mt-1 font-semibold text-slate-800">{{ formatDate(polygon.created_at) }}</dd>
                </div>
                <div>
                  <dt class="text-slate-500">Zuletzt geändert</dt>
                  <dd class="mt-1 font-semibold text-slate-800">{{ formatDate(polygon.updated_at) }}</dd>
                </div>
              </dl>
              <NuxtLink
                class="mt-4 inline-flex min-h-11 items-center gap-1 font-bold text-[#154d73] hover:underline"
                :to="`/flaechen/${polygon.slug}`"
                :aria-label="`Details zu ${polygon.name} anzeigen`"
              >
                Details anzeigen <ArrowRight class="size-4" aria-hidden="true" />
              </NuxtLink>
            </article>
          </div>

          <div class="hidden overflow-x-auto md:block">
            <table class="w-full min-w-[720px] text-left text-sm">
              <caption class="sr-only">Gefilterte und sortierte Liste Ihrer Flächen</caption>
              <thead class="bg-[#eef2f3] text-xs uppercase tracking-wide text-[#687176]">
                <tr>
                  <th class="px-5 py-3" scope="col">Name</th>
                  <th class="px-5 py-3" scope="col">Kategorie</th>
                  <th class="px-5 py-3" scope="col">Erstellt am</th>
                  <th class="px-5 py-3" scope="col">Zuletzt geändert</th>
                  <th class="px-5 py-3 text-right" scope="col">Aktion</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="polygon in visiblePolygons" :key="polygon.id" class="border-t border-[#edf0f1] hover:bg-slate-50/70">
                  <td class="px-5 py-4 font-bold text-slate-950">{{ polygon.name }}</td>
                  <td class="px-5 py-4"><PolygonCategoryBadge :category="polygon.category" /></td>
                  <td class="px-5 py-4 text-slate-600">{{ formatDate(polygon.created_at) }}</td>
                  <td class="px-5 py-4 text-slate-600">{{ formatDate(polygon.updated_at) }}</td>
                  <td class="px-5 py-4 text-right">
                    <NuxtLink
                      class="inline-flex min-h-11 items-center gap-1 font-bold text-[#154d73] hover:underline"
                      :to="`/flaechen/${polygon.slug}`"
                      :aria-label="`Details zu ${polygon.name} anzeigen`"
                    >
                      Details <ArrowRight class="size-4" aria-hidden="true" />
                    </NuxtLink>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </Card>
    </template>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { ArrowRight, Search, X } from '@lucide/vue'
import type { UserPolygon } from '~/types/geo'
import { getIndustryLabel } from '~/utils/industries'
import {
  defaultPolygonSort,
  filterAndSortPolygons,
  isPolygonSort,
  polygonSortOptions,
  type PolygonSort
} from '~/utils/polygonManagement'
import { polygonSchema } from '~/utils/validation'

definePageMeta({ middleware: 'auth' })

const { request } = useApi()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const polygons = ref<UserPolygon[]>([])
const loading = ref(true)
const error = ref(false)

function queryValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

const searchQuery = ref(queryValue(route.query.q))
const selectedCategory = ref(queryValue(route.query.category))
const initialSort = queryValue(route.query.sort)
const sortBy = ref<PolygonSort>(isPolygonSort(initialSort) ? initialSort : defaultPolygonSort)

const categoryOptions = computed(() => [...new Set(polygons.value.map(polygon => polygon.category))]
  .map(value => ({ value, label: getIndustryLabel(value) }))
  .sort((left, right) => left.label.localeCompare(right.label, 'de-DE', { sensitivity: 'base' })))

const categoryCount = computed(() => categoryOptions.value.length)
const visiblePolygons = computed(() => filterAndSortPolygons(
  polygons.value,
  searchQuery.value,
  selectedCategory.value,
  sortBy.value
))
const hasActiveFilters = computed(() => Boolean(searchQuery.value.trim() || selectedCategory.value))
const latestUpdatedDate = computed(() => {
  const latest = polygons.value.reduce<string | null>((current, polygon) => {
    if (!current || Date.parse(polygon.updated_at) > Date.parse(current)) return polygon.updated_at
    return current
  }, null)
  return latest ? formatDate(latest) : '—'
})
const resultLabel = computed(() => {
  const visible = visiblePolygons.value.length
  const total = polygons.value.length
  if (hasActiveFilters.value) return `${visible} von ${total} ${total === 1 ? 'Fläche' : 'Flächen'}`
  return `${visible} ${visible === 1 ? 'Fläche' : 'Flächen'}`
})
const noResultsDescription = computed(() => {
  if (searchQuery.value.trim()) return `Für „${searchQuery.value.trim()}“ wurden mit den gewählten Filtern keine passenden Flächen gefunden.`
  return 'Für die gewählte Kategorie wurden keine passenden Flächen gefunden.'
})

async function loadPolygons() {
  loading.value = true
  error.value = false
  try {
    const result = await request<unknown[]>('/users/me/polygons')
    polygons.value = result.map(item => polygonSchema.parse(item))
    if (selectedCategory.value && !polygons.value.some(polygon => polygon.category === selectedCategory.value)) {
      selectedCategory.value = ''
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchQuery.value = ''
  selectedCategory.value = ''
}

const dateFormatter = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date)
}

function queryState(q: unknown, category: unknown, sort: unknown) {
  return JSON.stringify([queryValue(q), queryValue(category), queryValue(sort)])
}

let pendingQueryState: string | null = null

watch([searchQuery, selectedCategory, sortBy], ([q, category, sort]) => {
  const nextQuery = { ...route.query }
  if (q.trim()) nextQuery.q = q.trim()
  else delete nextQuery.q
  if (category) nextQuery.category = category
  else delete nextQuery.category
  if (sort !== defaultPolygonSort) nextQuery.sort = sort
  else delete nextQuery.sort

  const currentQ = queryValue(route.query.q)
  const currentCategory = queryValue(route.query.category)
  const currentSort = queryValue(route.query.sort)
  if (currentQ === queryValue(nextQuery.q)
    && currentCategory === queryValue(nextQuery.category)
    && currentSort === queryValue(nextQuery.sort)) return
  const targetState = queryState(nextQuery.q, nextQuery.category, nextQuery.sort)
  pendingQueryState = targetState
  void router.replace({ query: nextQuery }).finally(() => {
    if (pendingQueryState === targetState) pendingQueryState = null
  })
})

watch(() => [route.query.q, route.query.category, route.query.sort], ([q, category, sort]) => {
  const routeState = queryState(q, category, sort)
  if (pendingQueryState && routeState !== pendingQueryState) return
  if (pendingQueryState === routeState) pendingQueryState = null
  searchQuery.value = queryValue(q)
  selectedCategory.value = queryValue(category)
  const routeSort = queryValue(sort)
  sortBy.value = isPolygonSort(routeSort) ? routeSort : defaultPolygonSort
})

onMounted(loadPolygons)

usePageSeo({
  title: 'Meine Flächen',
  description: 'Eigene angelegte Flächen verwalten.',
  path: '/meine-flaechen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
