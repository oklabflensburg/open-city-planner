<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="location-analysis-title">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wide text-[#154d73]">Standortanalyse</p>
        <h2 id="location-analysis-title" class="mt-1 text-lg font-bold text-slate-950">Standort &amp; Umfeld</h2>
      </div>
      <div class="flex rounded-xl border border-slate-200 p-1" aria-label="Analyseradius">
        <button v-for="value in radii" :key="value" class="h-10 cursor-pointer rounded-lg px-3 text-xs font-bold" :class="radius === value ? 'bg-[#154d73] text-white' : 'text-slate-600 hover:bg-slate-50'" type="button" :aria-pressed="radius === value" @click="load(value)">{{ value < 1000 ? `${value} m` : '1 km' }}</button>
      </div>
    </div>
    <div v-if="loading" class="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Standortdaten werden geladen">
      <div v-for="item in 4" :key="item" class="h-20 animate-pulse rounded-xl bg-slate-100" />
    </div>
    <div v-else-if="error" class="mt-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-800">
      <p>Standortdaten konnten nicht geladen werden.</p>
      <button class="mt-2 cursor-pointer font-bold underline" type="button" @click="load(radius)">Erneut versuchen</button>
    </div>
    <template v-else-if="data">
      <p v-if="data.nearest_public_transport" class="mt-5 rounded-xl bg-sky-50 p-4 text-sm text-slate-700">
        Nächster ÖPNV: <strong>{{ data.nearest_public_transport.name || 'Haltestelle' }}</strong> · {{ Math.round(data.nearest_public_transport.distance_m) }} m
      </p>
      <dl v-if="data.poi_counts.length" class="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <div v-for="poi in data.poi_counts" :key="poi.category" class="rounded-xl border border-slate-200 p-3">
          <dt class="text-xs text-slate-500">{{ poi.label }}</dt>
          <dd class="mt-1 text-xl font-bold tabular-nums text-slate-900">{{ poi.count }}</dd>
        </div>
      </dl>
      <p v-else class="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Für diesen Radius liegen keine POI-Daten vor.</p>
      <p class="mt-4 text-xs text-slate-500">Quelle: {{ data.source }}<template v-if="data.reference_date"> · Stand: {{ formatDate(data.reference_date) }}</template></p>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { LocationAnalysis } from '~/types/analytics'

const props = defineProps<{ slug: string }>()
const radii = [250, 500, 1000]
const radius = ref(500)
const data = ref<LocationAnalysis | null>(null)
const loading = ref(false)
const error = ref('')

onMounted(() => load(radius.value))

async function load(value: number) {
  radius.value = value
  loading.value = true
  error.value = ''
  try { data.value = await usePolygonApi().locationBySlug(props.slug, value) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Standortdaten konnten nicht geladen werden.' }
  finally { loading.value = false }
}

function formatDate(value: string) { return new Intl.DateTimeFormat('de-DE').format(new Date(value)) }
</script>
