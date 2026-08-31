<template>
  <section aria-labelledby="compare-areas-title">
    <h2 id="compare-areas-title" class="text-xs font-black uppercase tracking-wide text-slate-600">Vergleichsgebiete</h2>
    <ul v-if="selectedAreas.length" class="mt-3 space-y-2">
      <li v-for="(area, index) in selectedAreas" :key="area.id" class="flex min-w-0 items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
        <span class="size-3 shrink-0 rounded-full" :style="{ backgroundColor: colors[index] }" aria-hidden="true" />
        <span class="min-w-0 flex-1"><strong class="block truncate text-sm text-slate-950">{{ area.name }}</strong><span class="text-xs text-slate-500">{{ typeLabel(area.area_type) }}</span></span>
        <button class="grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-slate-500 hover:bg-white hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" :aria-label="`${area.name} aus Vergleich entfernen`" @click="$emit('remove', area.slug)"><X class="size-4" aria-hidden="true" /></button>
      </li>
    </ul>
    <p v-else class="mt-3 text-sm leading-6 text-slate-600">Wählen Sie zwei Gebiete oder ein Gebiet mit Gesamtstadt-Referenz.</p>

    <div class="mt-4">
      <label class="field-label" for="compare-area-search">Gebiet hinzufügen</label>
      <div class="relative mt-1">
        <Search class="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400" aria-hidden="true" />
        <input
          id="compare-area-search"
          ref="searchInput"
          v-model="search"
          class="field-input pl-9"
          type="search"
          autocomplete="off"
          placeholder="Gemeinde, Stadtteil oder Quartier"
          :disabled="selectedSlugs.length >= max"
          aria-controls="compare-area-results"
          @keydown.down.prevent="focusFirst"
          @keydown.enter.prevent="addFirst"
          @keydown.escape="search = ''"
        >
      </div>
      <p v-if="selectedSlugs.length >= max" class="mt-2 text-xs font-semibold text-amber-700">Maximal {{ max }} Gebiete können verglichen werden.</p>
    </div>

    <div id="compare-area-results" ref="results" class="mt-3 max-h-72 overflow-y-auto overscroll-contain" aria-live="polite">
      <p v-if="loading" class="py-4 text-sm text-slate-500">Gebiete werden geladen …</p>
      <p v-else-if="error" class="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{{ error }}</p>
      <p v-else-if="!available.length && search" class="py-4 text-sm text-slate-500">Kein passendes Gebiet gefunden.</p>
      <section v-for="group in groups" :key="group.type" class="mb-3 last:mb-0" :aria-labelledby="`compare-group-${group.type}`">
        <h3 :id="`compare-group-${group.type}`" class="sticky top-0 bg-white py-1 text-[11px] font-black uppercase tracking-wide text-slate-500">{{ group.label }}</h3>
        <button
          v-for="area in group.areas"
          :key="area.id"
          data-compare-area-option
          class="flex min-h-11 w-full min-w-0 cursor-pointer items-center rounded-lg px-2 text-left hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]"
          type="button"
          @click="add(area.slug)"
        >
          <span class="min-w-0"><strong class="block text-sm text-slate-900">{{ area.name }}</strong><span class="block text-xs text-slate-500">{{ optionContext(area) }}</span></span>
        </button>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Search, X } from '@lucide/vue'
import type { PublicAreaReference, PublicAreaType } from '~/types/publicAreaReference'

const props = withDefaults(defineProps<{
  areas: PublicAreaReference[]
  selectedSlugs: string[]
  colors: string[]
  loading?: boolean
  error?: string | null
  max?: number
}>(), { loading: false, error: null, max: 4 })
const emit = defineEmits<{ add: [slug: string], remove: [slug: string] }>()
const search = ref('')
const results = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const selectedAreas = computed(() => props.selectedSlugs.flatMap(slug => {
  const area = props.areas.find(candidate => candidate.slug === slug)
  return area ? [area] : []
}))
const available = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase('de-DE')
  return props.areas.filter(area => !props.selectedSlugs.includes(area.slug) && (!needle || [area.name, area.slug, area.parent_name].some(value => value?.toLocaleLowerCase('de-DE').includes(needle))))
})
const groupOrder: Array<{ type: PublicAreaType, label: string }> = [
  { type: 'MUNICIPALITY', label: 'Gemeinden' }, { type: 'DISTRICT', label: 'Stadtteile' }, { type: 'QUARTER', label: 'Quartiere' }
]
const groups = computed(() => groupOrder.map(group => ({ ...group, areas: available.value.filter(area => area.area_type === group.type) })).filter(group => group.areas.length))

function typeLabel(type: PublicAreaType) {
  return ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[type]
}
function optionContext(area: PublicAreaReference) {
  return [typeLabel(area.area_type), area.parent_name].filter(Boolean).join(' · ')
}
function add(slug: string) {
  if (props.selectedSlugs.length >= props.max) return
  emit('add', slug)
  search.value = ''
  nextTick(() => searchInput.value?.focus())
}
function addFirst() {
  const first = available.value[0]
  if (first) add(first.slug)
}
function focusFirst() {
  results.value?.querySelector<HTMLButtonElement>('[data-compare-area-option]')?.focus()
}
</script>
