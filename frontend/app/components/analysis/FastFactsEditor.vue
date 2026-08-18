<template>
  <section aria-labelledby="metrics-editor-title">
    <h2 id="metrics-editor-title" class="text-lg font-bold text-slate-800">Werte und Datenquelle</h2>
    <p class="mt-1 text-sm text-slate-600">Leere Felder werden als „keine Daten“ gespeichert und öffentlich mit einem Gedankenstrich dargestellt.</p>

    <div v-if="analytics.managementLoading" class="mt-3 h-48 animate-pulse rounded-xl bg-slate-100" />
    <div v-else-if="analytics.managementError" class="mt-3 rounded-xl bg-rose-50 p-3 text-xs text-rose-800">
      <p>{{ analytics.managementError }}</p>
      <button class="mt-2 cursor-pointer font-bold underline" type="button" @click="analytics.loadManagement()">Erneut versuchen</button>
    </div>
    <form v-else class="mt-3 space-y-3" @submit.prevent="save">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 min-[1440px]:grid-cols-2">
        <label v-for="field in numberFields" :key="field.key" class="block text-xs font-semibold text-slate-700">
          {{ field.label }}
          <span class="relative mt-1 block">
            <input v-model="draft[field.key]" class="min-h-11 w-full cursor-text rounded-lg border border-slate-300 bg-white px-3 pr-7 text-sm font-normal text-slate-900 outline-none focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/15" type="number" step="0.01" min="0" :max="field.percent ? 100 : undefined">
            <span v-if="field.percent" class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">%</span>
          </span>
          <span v-if="analytics.validationErrors[field.key]" class="mt-1 block font-normal text-rose-700">{{ analytics.validationErrors[field.key] }}</span>
        </label>
      </div>
      <label class="block text-xs font-semibold text-slate-700">
        Datenstand
        <input v-model="draft.reference_date" class="mt-1 min-h-11 w-full cursor-text rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 outline-none focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/15" type="date">
      </label>
      <label class="block text-xs font-semibold text-slate-700">
        Quelle
        <input v-model="draft.source" class="mt-1 min-h-11 w-full cursor-text rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 outline-none focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/15" maxlength="1000">
      </label>
      <label class="block text-xs font-semibold text-slate-700">
        Interner Hinweis
        <textarea v-model="draft.notes" class="mt-1 min-h-24 w-full cursor-text resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-900 outline-none focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/15" maxlength="10000" />
      </label>
      <p v-if="analytics.saveError" class="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert">{{ analytics.saveError }}</p>
      <p v-if="savedMessage" class="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800" role="status">{{ savedMessage }}</p>
      <div class="flex justify-end gap-2">
        <button class="min-h-11 cursor-pointer rounded-lg border border-slate-300 px-3 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50" type="button" :disabled="analytics.saving" @click="resetDraft">Zurücksetzen</button>
        <button class="min-h-11 cursor-pointer rounded-lg bg-[#154d73] px-4 text-xs font-bold text-white hover:bg-[#0f3f61] disabled:cursor-not-allowed disabled:opacity-60" type="submit" :disabled="analytics.saving">
          {{ analytics.saving ? 'Speichert …' : 'Speichern' }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import type { CityMetricsUpdate, CityMetricsVerwaltung } from '~/types/analytics'

type NumericKey = 'vacancy_rate' | 'chain_store_rate' | 'centrality_index' | 'purchasing_power_index'
type Draft = Record<NumericKey, string | number> & { reference_date: string; source: string; notes: string }

const analytics = useAnalyticsStore()
const savedMessage = ref('')
const draft = reactive<Draft>({
  vacancy_rate: '',
  chain_store_rate: '',
  centrality_index: '',
  purchasing_power_index: '',
  reference_date: '',
  source: '',
  notes: ''
})
const numberFields: Array<{ key: NumericKey; label: string; percent: boolean }> = [
  { key: 'vacancy_rate', label: 'Leerstand', percent: true },
  { key: 'chain_store_rate', label: 'Filialisierung', percent: true },
  { key: 'centrality_index', label: 'Zentralität (Index)', percent: false },
  { key: 'purchasing_power_index', label: 'Kaufkraft (Index)', percent: false }
]

watch(() => analytics.management, fillDraft, { immediate: true })

onMounted(() => analytics.loadManagement())

function fillDraft(metrics: CityMetricsVerwaltung | null) {
  if (!metrics) return
  for (const field of numberFields) draft[field.key] = metrics[field.key]?.toString() || ''
  draft.reference_date = metrics.reference_date || ''
  draft.source = metrics.source || ''
  draft.notes = metrics.notes || ''
}

function nullableNumber(value: string | number) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const normalized = value.trim()
  return normalized === '' ? null : Number(normalized)
}

function resetDraft() {
  fillDraft(analytics.management)
  analytics.saveError = null
  analytics.validationErrors = {}
  savedMessage.value = ''
}

async function save() {
  savedMessage.value = ''
  const payload: CityMetricsUpdate = {
    vacancy_rate: nullableNumber(draft.vacancy_rate),
    chain_store_rate: nullableNumber(draft.chain_store_rate),
    centrality_index: nullableNumber(draft.centrality_index),
    purchasing_power_index: nullableNumber(draft.purchasing_power_index),
    reference_date: draft.reference_date || null,
    source: draft.source.trim() || null,
    notes: draft.notes.trim() || null
  }
  if (await analytics.updateFastFacts(payload)) savedMessage.value = 'Die Kennzahlen wurden gespeichert.'
}
</script>
