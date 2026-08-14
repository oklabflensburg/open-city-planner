<template>
  <details class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" @toggle="handleToggle">
    <summary class="cursor-pointer text-lg font-bold text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]">Vergleichbare Flächen</summary>
    <p class="mt-2 text-sm text-slate-600">Transparent verglichen nach Branche, Größe, Etage und räumlicher Nähe.</p>
    <div v-if="loading" class="mt-5 h-24 animate-pulse rounded-xl bg-slate-100" />
    <div v-else-if="error" class="mt-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{{ error }}</div>
    <ul v-else-if="data?.items.length" class="mt-5 divide-y divide-slate-200">
      <li v-for="item in data.items" :key="item.slug" class="py-4 first:pt-0 last:pb-0">
        <NuxtLink class="font-bold text-[#154d73] hover:underline" :to="`/flaechen/${item.slug}`">{{ item.title }}</NuxtLink>
        <p class="mt-1 text-xs text-slate-500">{{ Math.round(item.area_m2) }} m² · {{ Math.round(item.distance_m) }} m entfernt · Ähnlichkeit {{ Math.round(item.similarity_score * 100) }} %</p>
      </li>
    </ul>
    <p v-else-if="loaded" class="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Keine vergleichbaren Flächen im Umkreis gefunden.</p>
  </details>
</template>

<script setup lang="ts">
import type { ComparableResult } from '~/types/analytics'

const props = defineProps<{ slug: string }>()
const data = ref<ComparableResult | null>(null)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

async function handleToggle(event: Event) {
  if (!(event.currentTarget as HTMLDetailsElement).open || loaded.value || loading.value) return
  loading.value = true
  try { data.value = await usePolygonApi().comparablesBySlug(props.slug) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Vergleichsflächen konnten nicht geladen werden.' }
  finally { loading.value = false; loaded.value = true }
}
</script>
