<template>
  <ContentPageShell
    class="min-w-0 max-w-full"
    title="Auditlog"
    description="Administrative Änderungen nachvollziehen und unveränderliche Ereignisdetails prüfen."
    eyebrow="Administration"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Administration', to: '/admin/benutzer' }, { label: 'Auditlog' }]"
    max-width="wide"
  >
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>

    <Card class="min-w-0 max-w-full p-4 sm:p-6">
      <div class="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1.1fr)_minmax(0,1.1fr)_minmax(0,.8fr)_minmax(0,.8fr)_minmax(0,.65fr)]">
        <label class="min-w-0">
          <span class="field-label">Auditlog durchsuchen</span>
          <span class="relative block min-w-0"><Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><input v-model="filters.search" type="search" class="field-input min-w-0 max-w-full pl-10" placeholder="Aktion, Name oder E-Mail" autocomplete="off"></span>
        </label>
        <label class="min-w-0"><span class="field-label">Aktion</span><select v-model="filters.action" class="field-input min-w-0 max-w-full" @change="filterChanged"><option value="">Alle Aktionen</option><option v-for="action in availableActions" :key="action" :value="action">{{ auditActionLabel(action) }}</option></select></label>
        <label class="min-w-0"><span class="field-label">Ausgeführt von</span><select v-model="filters.userId" class="field-input min-w-0 max-w-full" @change="filterChanged"><option value="">Alle Benutzer</option><option v-for="actor in actors" :key="actor.id" :value="actor.id">{{ actorName(actor) }}</option></select></label>
        <label class="min-w-0"><span class="field-label">Von</span><input v-model="filters.dateFrom" type="date" class="field-input min-w-0 max-w-full" @change="filterChanged"></label>
        <label class="min-w-0"><span class="field-label">Bis</span><input v-model="filters.dateTo" type="date" class="field-input min-w-0 max-w-full" @change="filterChanged"></label>
        <label class="min-w-0"><span class="field-label">Pro Seite</span><select v-model.number="filters.pageSize" class="field-input min-w-0 max-w-full" @change="filterChanged"><option :value="25">25</option><option :value="50">50</option><option :value="100">100</option></select></label>
      </div>
    </Card>

    <div class="mt-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm font-semibold text-slate-600" aria-live="polite">{{ total }} {{ total === 1 ? 'Ereignis' : 'Ereignisse' }}</p>
      <Button v-if="hasFilters" @click="clearFilters"><RotateCcw class="size-4" /> Filter zurücksetzen</Button>
    </div>

    <div v-if="loading" class="mt-5 space-y-3" role="status" aria-label="Auditlog wird geladen">
      <div v-for="index in 6" :key="index" class="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
    <Card v-else-if="error" class="mt-5 border-rose-200 p-8 text-center">
      <CircleAlert class="mx-auto size-9 text-rose-600" />
      <h2 class="mt-4 text-lg font-bold text-slate-950">Auditlog konnte nicht geladen werden</h2>
      <p class="mt-2 text-sm text-rose-800" role="alert">{{ error }}</p>
      <Button class="mt-5" @click="load"><RefreshCw class="size-4" /> Erneut versuchen</Button>
    </Card>
    <AuditLogList v-else-if="items.length" class="mt-5" :items="items" @select="selectedItem = $event" />
    <Card v-else class="mt-5 p-10 text-center">
      <ScrollText class="mx-auto size-9 text-slate-400" />
      <h2 class="mt-4 text-lg font-bold text-slate-950">Keine Audit-Ereignisse gefunden</h2>
      <p class="mt-2 text-sm text-slate-600">Für den gewählten Zeitraum und die Filter gibt es keine Einträge.</p>
      <Button v-if="hasFilters" class="mt-5" @click="clearFilters"><RotateCcw class="size-4" /> Filter zurücksetzen</Button>
    </Card>

    <nav v-if="pages > 1" class="mt-6 flex min-w-0 flex-wrap items-center justify-between gap-3" aria-label="Seitennavigation">
      <Button :disabled="filters.page <= 1 || loading" @click="changePage(filters.page - 1)"><ChevronLeft class="size-4" /> Zurück</Button>
      <span class="text-center text-sm font-semibold text-slate-600">Seite {{ filters.page }} von {{ pages }}</span>
      <Button :disabled="filters.page >= pages || loading" @click="changePage(filters.page + 1)">Weiter <ChevronRight class="size-4" /></Button>
    </nav>

    <AuditLogDetailModal :item="selectedItem" @close="selectedItem = null" />
  </ContentPageShell>
</template>

<script setup lang="ts">
import { ChevronLeft, ChevronRight, CircleAlert, RefreshCw, RotateCcw, ScrollText, Search } from 'lucide-vue-next'
import type { AdminUser, AuditLogItem } from '~/types/admin'
import { auditActionLabel } from '~/utils/auditLog'

definePageMeta({ middleware: 'superuser' })

const route = useRoute()
const router = useRouter()
const { items, actors, availableActions, total, pages, filters, loading, error, load, loadActors, resetFilters } = useAuditLog()
const selectedItem = ref<AuditLogItem | null>(null)
const initialized = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | undefined

const hasFilters = computed(() => Boolean(filters.search || filters.action || filters.userId || filters.dateFrom || filters.dateTo || filters.pageSize !== 50))

function queryValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function applyRouteQuery() {
  filters.search = queryValue(route.query.search)
  filters.action = queryValue(route.query.action)
  filters.userId = queryValue(route.query.user_id)
  filters.dateFrom = queryValue(route.query.date_from)
  filters.dateTo = queryValue(route.query.date_to)
  const page = Number(queryValue(route.query.page))
  const pageSize = Number(queryValue(route.query.page_size))
  filters.page = Number.isInteger(page) && page > 0 ? page : 1
  filters.pageSize = [25, 50, 100].includes(pageSize) ? pageSize : 50
}

function routeQuery() {
  return Object.fromEntries(Object.entries({
    search: filters.search.trim() || undefined,
    action: filters.action || undefined,
    user_id: filters.userId || undefined,
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    page: filters.page > 1 ? String(filters.page) : undefined,
    page_size: filters.pageSize !== 50 ? String(filters.pageSize) : undefined
  }).filter((entry): entry is [string, string] => Boolean(entry[1])))
}

async function commitFilters() {
  const nextQuery = routeQuery()
  const currentQuery = Object.fromEntries(Object.entries(route.query).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
  if (JSON.stringify(nextQuery) === JSON.stringify(currentQuery)) await load()
  else await router.replace({ query: nextQuery })
}

function filterChanged() {
  filters.page = 1
  void commitFilters()
}

function changePage(page: number) {
  filters.page = page
  void commitFilters()
}

function clearFilters() {
  resetFilters()
  void commitFilters()
}

function actorName(actor: AdminUser) {
  return actor.display_name || [actor.first_name, actor.last_name].filter(Boolean).join(' ') || actor.email
}

watch(() => route.fullPath, async () => {
  if (!initialized.value) return
  applyRouteQuery()
  selectedItem.value = null
  await load()
})

watch(() => filters.search, () => {
  if (!initialized.value) return
  filters.page = 1
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { void commitFilters() }, 400)
})

onMounted(async () => {
  applyRouteQuery()
  initialized.value = true
  try { await loadActors() } catch { /* The log remains usable if the optional actor list fails. */ }
  await load()
})
onBeforeUnmount(() => { if (searchTimer) clearTimeout(searchTimer) })

usePageSeo({
  title: 'Auditlog',
  description: 'Geschütztes administratives Auditlog für Superuser.',
  path: '/admin/audit-log',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
