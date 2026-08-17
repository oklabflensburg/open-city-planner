<template>
  <aside class="min-w-0 bg-[var(--c-surface)] lg:h-full lg:min-h-0 lg:overflow-hidden">
    <div class="flex min-w-0 flex-col gap-2 pr-1 lg:h-full lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain">
      <header class="sticky top-0 z-10 rounded-2xl border border-slate-200/80 bg-white px-4 py-3 shadow-sm">
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-sm font-black text-slate-900">Analyse</h2>
          <span v-if="filters.activeFilterCount" class="rounded-full bg-[#e2edf4] px-2 py-0.5 text-[11px] font-black text-[#154d73]">{{ filters.activeFilterCount }} Filter aktiv</span>
        </div>
        <p class="mt-1 text-[11px] leading-4 text-slate-500">Aktueller Filterzustand · Stadtplanner und OpenStreetMap</p>
        <p class="mt-1 text-[11px] font-semibold text-slate-700">{{ polygonCount }} gepflegte Flächen · {{ osmCount }} passende OSM-Objekte im Ausschnitt</p>
      </header>
      <MapSelectionContent />
      <FastFacts />
      <ClientOnly>
        <LazyIndustryChart />
        <LazyDistributionCharts />
        <template #fallback><div class="civic-card h-52 animate-pulse bg-white" aria-label="Diagramme werden geladen" /></template>
      </ClientOnly>
      <ViewportOsmSummary />
      <RentTable />
    </div>
  </aside>
</template>

<script setup lang="ts">
const filters = useFilterStore()
const polygonCount = computed(() => usePolygonStore().polygons.length)
const osmCount = computed(() => useOsmViewportStore().data?.meta.business_count || 0)
</script>
