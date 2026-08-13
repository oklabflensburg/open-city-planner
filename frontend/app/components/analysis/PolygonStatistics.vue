<template>
  <Card v-if="polygon" class="p-4">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Ausgewählte Fläche</p>
        <h2 class="mt-1 text-sm font-bold text-slate-900">{{ polygon.name }}</h2>
        <p v-if="polygon.address_display_name" class="mt-1 text-xs leading-5 text-slate-500">{{ polygon.address_display_name }}</p>
      </div>
      <button class="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" aria-label="Auswahl schließen" @click="closeSelection">
        <X class="size-4" />
      </button>
    </div>
    <dl class="mt-4 grid grid-cols-2 gap-3 text-xs">
      <div>
        <dt class="text-slate-500">Branche</dt>
        <dd class="mt-1 font-semibold text-slate-800">{{ industryLabel }}</dd>
      </div>
      <div>
        <dt class="text-slate-500">Größe</dt>
        <dd class="mt-1 font-semibold text-slate-800">{{ polygon.area_size || 'Nicht angegeben' }}</dd>
      </div>
      <div>
        <dt class="text-slate-500">Etage</dt>
        <dd class="mt-1 font-semibold text-slate-800">{{ polygon.floor || 'Nicht angegeben' }}</dd>
      </div>
      <div v-if="store.selectedMetrics">
        <dt class="text-slate-500">Fläche</dt>
        <dd class="mt-1 font-semibold text-slate-800">{{ Math.round(store.selectedMetrics.area_m2).toLocaleString('de-DE') }} m²</dd>
      </div>
    </dl>
    <PolygonOsmInfo class="mt-4 border-t border-slate-200 pt-4" :info="osm.data.value" :loading="osm.loading.value" :error="osm.error.value" compact @retry="osm.retry" />
    <NuxtLink class="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-lg bg-[#154d73] px-4 text-xs font-bold text-white transition hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :to="`/flaechen/${polygon.slug}`">
      Details anzeigen
      <ArrowRight class="ml-2 size-4" />
    </NuxtLink>
  </Card>
</template>

<script setup lang="ts">
import { ArrowRight, X } from 'lucide-vue-next'
import { getIndustryLabel } from '~/utils/industries'

const store = usePolygonStore()
const mapStore = useMapStore()
const polygon = computed(() => store.selectedPolygon)
const industryLabel = computed(() => getIndustryLabel(polygon.value?.category))
const osm = usePolygonOsmInfo()

watch(polygon, (selected) => {
  if (!selected) {
    osm.clear()
    return
  }
  void osm.loadBySlug({ id: selected.id, slug: selected.slug, updatedAt: selected.updated_at })
}, { immediate: true })

function closeSelection() {
  store.clearSelection()
  mapStore.analysisDrawerOpen = false
}
</script>
