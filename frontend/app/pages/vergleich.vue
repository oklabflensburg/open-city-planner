<template>
  <ContentPageShell title="Standorte vergleichen" description="Vergleichen Sie die aktuelle Kartenfilterung mit allen erfassten Flächen der Gesamtstadt." eyebrow="Marktanalyse" :breadcrumbs="[{ label: 'Karte', to: '/' }, { label: 'Vergleich' }]" max-width="wide">
    <div class="grid items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <Card class="space-y-6 p-5"><AreaFilter /><FloorFilter /><IndustryFilter /><MarketStatusFilter /></Card>
      <Card class="p-5 sm:p-6"><MarketBenchmarks /></Card>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
const analytics = useAnalyticsStore()
const filter = useFilterStore()
let timer: ReturnType<typeof setTimeout> | undefined
onMounted(() => analytics.loadBenchmarks())
watch(() => [filter.selectedSize, filter.selectedFloor, ...filter.activeCategories, ...filter.occupancyStatuses, ...filter.businessStructures], () => {
  clearTimeout(timer)
  timer = setTimeout(() => analytics.loadBenchmarks(), 180)
})
onBeforeUnmount(() => clearTimeout(timer))
usePageSeo({ title: 'Standorte vergleichen', description: 'Öffentliche Marktbenchmarks für die erfassten Flächen in Flensburg.', path: '/vergleich' })
</script>
