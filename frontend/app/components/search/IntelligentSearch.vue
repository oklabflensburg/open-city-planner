<template>
  <section
    class="min-w-0"
    :class="embedded ? '' : 'rounded-2xl border border-slate-200/80 bg-white shadow-sm'"
    aria-label="Intelligente Kartensuche"
    data-intelligent-search
    :data-search-mode="compact ? 'compact' : 'panel'"
  >
    <div class="p-2.5" :class="assistantVisible && !compact ? 'border-b border-slate-200' : ''">
      <form class="flex min-w-0 items-center gap-1.5" role="search" @submit.prevent="submit">
        <Search class="ml-1 size-4 shrink-0 text-slate-500" aria-hidden="true" />
        <label class="sr-only" :for="inputId">Stadtplaner durchsuchen</label>
        <input
          :id="inputId"
          ref="input"
          v-model="search.query"
          class="min-h-10 min-w-0 flex-1 rounded-lg border-0 bg-transparent px-1.5 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:ring-0"
          type="search"
          maxlength="500"
          autocomplete="off"
          placeholder="Stadtplaner durchsuchen…"
          :aria-expanded="assistantVisible"
          :aria-controls="panelId"
          @focus="focused = true"
          @blur="focused = false"
          @keydown.esc.stop.prevent="handleEscape"
        >
        <button
          v-if="search.query"
          class="grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]"
          type="button"
          aria-label="Suchtext löschen"
          @click="clearQuery"
        >
          <X class="size-4" aria-hidden="true" />
        </button>
        <button
          class="grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg bg-[#154d73] text-white hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50"
          type="submit"
          :disabled="search.query.trim().length < 2"
          aria-label="Suche ausführen"
        >
          <LoaderCircle v-if="search.loading" class="size-4 animate-spin" aria-hidden="true" />
          <Search v-else class="size-4" aria-hidden="true" />
        </button>
      </form>
      <div class="mt-1 flex min-h-4 items-center gap-2 px-1 text-[11px] text-slate-500">
        <span v-if="search.loading" role="status" aria-live="polite">Suche wird ausgewertet…</span>
        <span v-else-if="activeSearchLabel" class="truncate">{{ activeSearchLabel }}</span>
        <span v-else>Frage stellen oder Befehl eingeben</span>
        <button v-if="compact && search.assistantOpen" class="ml-auto shrink-0 font-bold text-[#154d73]" type="button" @click="openPanel">Antwort öffnen</button>
      </div>
    </div>

    <p
      v-if="search.confirmation"
      class="mx-2.5 mb-2.5 flex items-start gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800"
      role="status"
      aria-live="polite"
      data-search-confirmation
    >
      <CheckCircle2 class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{{ search.confirmation }}</span>
    </p>

    <div v-if="!compact && focused && !assistantVisible" class="border-t border-slate-100 p-2.5" data-search-suggestions>
      <p class="px-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Vorschläge</p>
      <div class="mt-1.5 grid gap-1">
        <button v-for="example in examples" :key="example" class="flex min-h-9 cursor-pointer items-center justify-between rounded-lg px-2 text-left text-xs font-semibold text-slate-700 hover:bg-slate-100" type="button" @mousedown.prevent @click="runExample(example)">
          {{ example }} <ChevronRight class="size-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>

    <section
      v-if="!compact && assistantVisible"
      :id="panelId"
      class="min-h-0"
      aria-label="Stadtplaner-Antwort"
      data-assistant-panel
    >
      <header class="flex items-center border-b border-slate-200 px-3" data-assistant-tabs>
        <button class="min-h-10 border-b-2 px-2 text-xs font-bold" :class="search.activeTab === 'answer' ? 'border-[#154d73] text-[#154d73]' : 'border-transparent text-slate-500'" type="button" @click="search.activeTab = 'answer'">Antwort</button>
        <button class="min-h-10 border-b-2 px-2 text-xs font-bold" :class="search.activeTab === 'history' ? 'border-[#154d73] text-[#154d73]' : 'border-transparent text-slate-500'" type="button" @click="search.activeTab = 'history'">Verlauf</button>
        <button class="ml-auto grid size-9 cursor-pointer place-items-center rounded-lg text-slate-500 hover:bg-slate-100" type="button" aria-label="Assistant-Panel schließen" @click="closePanel">
          <X class="size-4" aria-hidden="true" />
        </button>
      </header>

      <div class="max-h-[min(52vh,34rem)] overflow-y-auto overscroll-contain p-3" data-assistant-scroll>
        <div v-if="search.activeTab === 'history'" class="grid gap-1.5" data-assistant-history>
          <p v-if="!search.history.length" class="text-xs text-slate-500">Noch keine Suchanfragen vorhanden.</p>
          <button v-for="entry in search.history" :key="entry.id" class="flex min-h-10 cursor-pointer items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50" type="button" @click="search.restoreHistory(entry)">
            <span class="truncate">{{ entry.query }}</span><ChevronRight class="size-4 shrink-0" aria-hidden="true" />
          </button>
        </div>

        <div v-else-if="search.loading" class="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-4 text-sm font-semibold text-slate-700" role="status" aria-live="polite">
          <LoaderCircle class="size-4 animate-spin text-[#154d73]" aria-hidden="true" /> Suche wird ausgewertet…
        </div>

        <p v-else-if="search.error" class="rounded-xl bg-rose-50 px-3 py-3 text-sm font-semibold text-rose-700" role="alert">{{ search.error }}</p>

        <article v-else-if="search.result" class="text-sm text-slate-700" role="status" aria-live="polite" data-search-answer>
          <h2 class="font-black text-slate-950">{{ search.result.presentation.title }}</h2>
          <p v-if="search.result.presentation.type !== 'KNOWLEDGE' || !search.result.presentation.items.length" class="mt-1 leading-5">{{ search.result.answer }}</p>
          <p v-if="['METRIC', 'STATISTIC_METRIC'].includes(search.result.presentation.type) && search.result.presentation.value !== null" class="mt-2 text-2xl font-black text-[#154d73]" data-assistant-metric>
            {{ formatValue(search.result.presentation.value) }}<span v-if="search.result.presentation.unit" class="text-sm">{{ ` ${unitLabel(search.result.presentation.unit)}` }}</span>
          </p>
          <div v-if="search.result.presentation.type === 'STATISTICS_OVERVIEW'" class="mt-3" data-assistant-statistics>
            <ul class="divide-y divide-slate-200 rounded-xl bg-slate-50 px-3 text-xs">
              <li v-for="(item, index) in search.result.presentation.items.slice(0, 12)" :key="itemKey(item, index)" class="flex items-start justify-between gap-3 py-2">
                <span><strong class="block text-slate-800">{{ stringValue(item.name) }}</strong><small class="text-slate-500">{{ stringValue(item.period) }}</small></span>
                <strong class="text-right text-[#154d73]">{{ statisticValue(item) }}</strong>
              </li>
            </ul>
          </div>
          <div v-else-if="search.result.presentation.type === 'STATISTIC_SERIES'" class="mt-3 overflow-x-auto" data-assistant-statistic-series>
            <table class="w-full text-left text-xs"><thead><tr><th class="py-1">Periode</th><th class="py-1 text-right">Wert</th></tr></thead><tbody><tr v-for="(item, index) in search.result.presentation.items" :key="itemKey(item, index)" class="border-t border-slate-200"><th class="py-1.5 font-semibold">{{ stringValue(item.period) }}</th><td class="text-right">{{ item.suppressed ? 'Unterdrückt' : statisticValue(item, search.result.presentation.unit) }}</td></tr></tbody></table>
          </div>
          <ul v-else-if="['METRIC_LIST', 'AREA_LIST'].includes(search.result.presentation.type)" class="mt-2 max-h-36 overflow-y-auto text-xs" data-assistant-list>
            <li v-for="(item, index) in search.result.presentation.items.slice(0, 8)" :key="itemKey(item, index)" class="border-t border-slate-200 py-1.5 first:border-0">{{ itemLabel(item) }}</li>
          </ul>
          <div v-else-if="search.result.presentation.type === 'FEATURE_LIST'" class="mt-3" data-assistant-features>
            <dl v-if="resultSummary.length" class="grid gap-1.5 rounded-xl bg-slate-50 p-3 text-xs">
              <div v-for="item in resultSummary" :key="item.label" class="flex justify-between gap-3"><dt class="text-slate-500">{{ item.label }}</dt><dd class="text-right font-bold text-slate-800">{{ item.value }}</dd></div>
            </dl>
            <button v-if="search.result.presentation.items.length" class="mt-2 min-h-9 cursor-pointer rounded-lg border border-slate-300 px-3 text-xs font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="detailsOpen = !detailsOpen">{{ detailsOpen ? 'Details ausblenden' : 'Details anzeigen' }}</button>
            <ul v-if="detailsOpen" class="mt-2 max-h-40 overflow-y-auto text-xs" data-assistant-list>
              <li v-for="(item, index) in search.result.presentation.items.slice(0, 20)" :key="itemKey(item, index)" class="border-t border-slate-200 py-1.5 first:border-0">{{ itemLabel(item) }}</li>
            </ul>
          </div>
          <div v-else-if="search.result.presentation.type === 'COMPARISON'" class="mt-3 overflow-x-auto" data-assistant-comparison>
            <table class="w-full text-left text-xs"><thead><tr><th class="py-1">Gebiet</th><th class="py-1">Leerstände</th><th class="py-1">Flächen</th></tr></thead><tbody><tr v-for="(item, index) in search.result.presentation.items" :key="itemKey(item, index)" class="border-t border-slate-200"><th class="py-1.5 font-semibold">{{ stringValue(item.name) }}</th><td>{{ metric(item, 'vacant_count') }}</td><td>{{ metric(item, 'polygon_count') }}</td></tr></tbody></table>
          </div>
          <div v-else-if="search.result.presentation.type === 'KNOWLEDGE'" class="mt-2 space-y-2 text-xs" data-assistant-knowledge>
            <div v-for="(item, index) in search.result.presentation.items" :key="itemKey(item, index)" class="border-t border-slate-200 pt-2 first:border-0 first:pt-0">
              <p v-if="knowledgeItemTitle(item)" class="font-bold text-slate-900">{{ knowledgeItemTitle(item) }}</p><p class="leading-5">{{ stringValue(item.description) }}</p>
              <p v-if="knowledgeSource(item)" class="mt-1 text-[11px] text-slate-500">{{ knowledgeSource(item) }}</p>
              <NuxtLink v-if="documentationRoute(item)" :to="documentationRoute(item)!" class="mt-1 inline-flex font-bold text-[#154d73] hover:underline">Mehr anzeigen</NuxtLink>
            </div>
          </div>
          <ul v-else-if="search.result.presentation.type === 'DATA_SOURCE_STATUS'" class="mt-2 text-xs" data-assistant-data-sources><li v-for="(item, index) in search.result.presentation.items" :key="itemKey(item, index)" class="border-t border-slate-200 py-1.5 first:border-0">{{ itemLabel(item) }}</li></ul>

          <dl v-if="statisticsMetadata.length" class="mt-3 grid gap-1 rounded-xl border border-slate-200 p-3 text-[11px]" data-assistant-statistics-metadata>
            <div v-for="item in statisticsMetadata" :key="item.label" class="flex justify-between gap-3"><dt class="text-slate-500">{{ item.label }}</dt><dd class="text-right font-semibold text-slate-700">{{ item.value }}</dd></div>
          </dl>
          <p v-if="statisticsInherited" class="mt-2 rounded-lg bg-amber-50 px-2.5 py-2 text-xs text-amber-900" data-assistant-statistics-inherited>Für dieses Gebiet werden Werte des übergeordneten Statistikgebiets verwendet.</p>

          <section v-for="(section, sectionIndex) in search.result.presentation.sections || []" :key="`${section.type}-${sectionIndex}`" class="mt-3 border-t border-slate-200 pt-3" data-assistant-result-section>
            <h3 class="text-xs font-black text-slate-900">{{ section.title }}</h3>
            <div v-if="section.type === 'KNOWLEDGE'" class="mt-1.5 space-y-2 text-xs" data-assistant-knowledge>
              <div v-for="(item, index) in section.items" :key="itemKey(item, index)">
                <p v-if="knowledgeItemTitle(item)" class="font-bold text-slate-900">{{ stringValue(item.title) }}</p>
                <p class="leading-5">{{ stringValue(item.description) }}</p>
                <p v-if="knowledgeSource(item)" class="mt-1 text-[11px] text-slate-500">{{ knowledgeSource(item) }}</p>
                <NuxtLink v-if="documentationRoute(item)" :to="documentationRoute(item)!" class="mt-1 inline-flex font-bold text-[#154d73] hover:underline">Mehr anzeigen</NuxtLink>
              </div>
            </div>
          </section>

          <div v-if="search.result.plan.response_mode === 'CLARIFICATION' && search.result.presentation.items.length" class="mt-3 flex flex-wrap gap-1.5" data-assistant-clarification>
            <button v-for="(item, index) in search.result.presentation.items" :key="itemKey(item, index)" class="rounded-full bg-[#edf4f8] px-3 py-1.5 text-xs font-bold text-[#154d73]" type="button" @click="runClarification(item)">{{ stringValue(item.name || item.label) }}</button>
          </div>
          <p v-if="search.result.sources_used.length" class="mt-3 text-[11px] text-slate-500">Datenbasis: {{ sourceLabels }}</p>
          <div v-if="search.result.follow_up_actions?.length" class="mt-3 grid gap-1.5" data-assistant-follow-ups>
            <p class="text-[11px] font-bold uppercase tracking-wide text-slate-500">Weitere Fragen</p>
            <button v-for="action in search.result.follow_up_actions" :key="`${action.type}-${action.query}`" class="flex min-h-9 cursor-pointer items-center justify-between rounded-lg border border-slate-200 px-3 text-left text-xs font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="runExample(action.query)">{{ action.label }}<ChevronRight class="size-4" aria-hidden="true" /></button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { CheckCircle2, ChevronRight, LoaderCircle, Search, X } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ compact?: boolean, embedded?: boolean }>(), {
  compact: false,
  embedded: false
})
const emit = defineEmits<{ open: [] }>()
const search = useSearchStore()
const input = ref<HTMLInputElement | null>(null)
const focused = ref(false)
const detailsOpen = ref(false)
const inputId = `intelligent-search-${useId()}`
const panelId = `assistant-panel-${useId()}`
const examples = ['Gastronomie in der Altstadt', 'Alle Stadtteile anzeigen', 'Nur Leerstände', 'Wie viele POIs gibt es in der Altstadt?']
const assistantVisible = computed(() => search.assistantOpen && (search.loading || search.result !== null || search.error !== null))
const activeSearchLabel = computed(() => {
  if (!search.result) return ''
  const area = search.result.context.active_area?.name
  const title = search.result.presentation.title
  return area && title !== area ? `${area} · ${title}` : title
})
const sourceLabels = computed(() => search.result?.sources_used.map(sourceLabel).filter((value, index, values) => values.indexOf(value) === index).join(', ') || '')
const resultSummary = computed(() => {
  const result = search.result
  if (!result || result.presentation.type !== 'FEATURE_LIST') return []
  const filters = result.context.active_filters
  return [
    { label: 'Treffer', value: formatValue(result.presentation.value ?? result.presentation.items.length) },
    ...(result.context.active_area ? [{ label: 'Gebiet', value: result.context.active_area.name }] : []),
    ...(filters.categories.length ? [{ label: 'Kategorie', value: filters.categories.join(', ') }] : []),
    ...(filters.occupancy_statuses.length ? [{ label: 'Status', value: filters.occupancy_statuses.join(', ') }] : []),
    ...(filters.sources.length ? [{ label: 'Quelle', value: filters.sources.join(' + ') }] : [])
  ]
})
const statisticsMetadata = computed(() => {
  const metadata = search.result?.presentation.metadata
  if (!metadata || !search.result?.presentation.type.startsWith('STATISTIC')) return []
  const source = asRecord(metadata.source)
  const requestedArea = asRecord(metadata.requested_area)
  const statisticsArea = asRecord(metadata.statistics_area)
  return [
    ...(requestedArea.name ? [{ label: 'Angefragtes Gebiet', value: String(requestedArea.name) }] : []),
    ...(statisticsArea.name ? [{ label: 'Statistikgebiet', value: String(statisticsArea.name) }] : []),
    ...(metadata.period ? [{ label: 'Stand', value: String(metadata.period) }] : []),
    ...(source.name ? [{ label: 'Quelle', value: String(source.name) }] : [])
  ]
})
const statisticsInherited = computed(() => Boolean(search.result?.presentation.metadata?.inherited_from_parent))

watch(() => search.result, () => { detailsOpen.value = false })

function submit() { void search.submit(search.query) }
function runExample(example: string) { search.query = example; void search.submit(example) }
function runClarification(item: Record<string, unknown>) {
  const value = String(item.slug || item.value || item.name || '')
  if (value.length >= 2) runExample(value)
}
function clearQuery() { search.clearQuery(); input.value?.focus() }
function closePanel() { search.closeAssistant(); nextTick(() => input.value?.focus()) }
function openPanel() { search.openAssistant(); emit('open') }
function handleEscape() {
  if (assistantVisible.value) closePanel()
  else focused.value = false
}
function formatValue(value: number | string) { return typeof value === 'number' ? new Intl.NumberFormat('de-DE').format(value) : value }
function stringValue(value: unknown) { return typeof value === 'string' ? value : '–' }
function asRecord(value: unknown): Record<string, unknown> { return value && typeof value === 'object' ? value as Record<string, unknown> : {} }
function itemKey(item: Record<string, unknown>, index: number) { return String(item.id || item.slug || item.key || index) }
function itemLabel(item: Record<string, unknown>) {
  const label = item.name || item.label || item.category || item.slug || 'Eintrag'
  const value = item.count ?? item.value
  return value === undefined || value === null ? String(label) : `${label}: ${formatValue(value as number | string)}`
}
function knowledgeItemTitle(item: Record<string, unknown>) {
  const title = typeof item.title === 'string' ? item.title : ''
  return title === search.result?.presentation.title ? '' : title
}
function unitLabel(unit: string) {
  return ({ persons: 'Personen', households: 'Haushalte', percent: '%' } as Record<string, string>)[unit] || unit
}
function statisticValue(item: Record<string, unknown>, fallbackUnit?: string | null) {
  const value = item.value
  if (typeof value !== 'number' && typeof value !== 'string') return '–'
  const unit = typeof item.unit === 'string' ? item.unit : fallbackUnit
  return `${formatValue(value)}${unit ? ` ${unitLabel(unit)}` : ''}`
}
function knowledgeSource(item: Record<string, unknown>) {
  const source = asRecord(item.source)
  return source.type === 'DOCUMENTATION' ? 'Quelle: Stadtplaner-Dokumentation' : ''
}
function documentationRoute(item: Record<string, unknown>) {
  const source = asRecord(item.source)
  const allowed = new Set([
    'docs/flensburg-statistics.md', 'docs/osm-data.md',
    'docs/intelligent-search.md', 'docs/stadtplaner-assistant.md'
  ])
  return source.type === 'DOCUMENTATION' && allowed.has(String(source.path)) ? '/dokumentation' : null
}
function metric(item: Record<string, unknown>, key: string) {
  const metrics = item.metrics
  if (!metrics || typeof metrics !== 'object') return '–'
  const value = (metrics as Record<string, unknown>)[key]
  return typeof value === 'number' ? formatValue(value) : '–'
}
function sourceLabel(source: { type: string, source?: string | null }) {
  const labels: Record<string, string> = {
    ANALYSIS_AREA_ANALYTICS: 'Stadtplaner Analytics', AREA_COMPARISON: 'Stadtplaner-Vergleich',
    STATISTICS: 'Kommunale Statistik', STATISTIC_SERIES: 'Kommunale Statistik-Zeitreihe',
    OSM: 'OpenStreetMap', STADTPLANNER: 'Stadtplaner', DOCUMENTATION: 'Projektdokumentation',
    OSM_AND_STADTPLANER: 'OpenStreetMap und Stadtplaner', KNOWLEDGE: 'Stadtplaner-Wissenskatalog'
  }
  return labels[source.type] || source.source || source.type
}
</script>
