<template>
  <div ref="root" class="relative">
    <label class="sr-only" for="docs-search">Dokumentation durchsuchen</label>
    <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
    <input
      id="docs-search"
      ref="input"
      v-model="query"
      class="h-11 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-20 text-sm text-slate-950 shadow-sm outline-none transition placeholder:text-slate-500 focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/20"
      type="search"
      autocomplete="off"
      placeholder="Dokumentation durchsuchen …"
      aria-controls="docs-search-results"
      :aria-expanded="showResults"
      @focus="focused = true"
      @keydown.esc="close"
    >
    <kbd class="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-semibold text-slate-500 sm:block">⌘/Ctrl K</kbd>

    <div v-if="showResults" id="docs-search-results" class="absolute inset-x-0 z-50 mt-2 max-h-[min(70vh,32rem)] overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-[0_20px_50px_rgba(15,23,42,0.18)]" role="listbox">
      <template v-if="results.length">
        <NuxtLink
          v-for="result in results"
          :key="`${result.page.slug}:${result.section?.id || 'page'}`"
          class="block rounded-lg px-3 py-3 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]"
          :to="resultPath(result)"
          role="option"
          @click="close"
        >
          <p class="text-sm font-bold text-slate-950">{{ result.page.title }}<span v-if="result.section" class="font-medium text-slate-500"> · {{ result.section.title }}</span></p>
          <p class="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{{ result.excerpt }}</p>
        </NuxtLink>
      </template>
      <div v-else class="px-3 py-5 text-center text-sm text-slate-600">
        <p class="font-semibold text-slate-800">Keine passenden Dokumentationsseiten gefunden.</p>
        <p class="mt-1">Versuchen Sie einen kürzeren Begriff, zum Beispiel „Karte“, „Fläche“ oder „Konto“.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next'
import type { DocumentationSearchResult } from '~/types/documentation'
import { documentationPath, searchDocumentation } from '~/utils/documentation'

const route = useRoute()
const query = ref(typeof route.query.suche === 'string' ? route.query.suche : '')
const focused = ref(false)
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const results = computed(() => searchDocumentation(query.value))
const showResults = computed(() => focused.value && query.value.trim().length > 0)

function resultPath(result: DocumentationSearchResult) {
  const path = documentationPath(result.page)
  return result.section ? `${path}#${result.section.id}` : path
}

function close() {
  focused.value = false
  input.value?.blur()
}

function handleShortcut(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    input.value?.focus()
    focused.value = true
  }
}

function handleOutsideClick(event: MouseEvent) {
  if (!root.value?.contains(event.target as Node)) focused.value = false
}

onMounted(() => {
  window.addEventListener('keydown', handleShortcut)
  window.addEventListener('click', handleOutsideClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleShortcut)
  window.removeEventListener('click', handleOutsideClick)
})
</script>
