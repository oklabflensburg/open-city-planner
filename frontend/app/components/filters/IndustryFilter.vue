<template>
  <div>
    <div class="mb-2 flex min-h-8 min-w-0 flex-wrap items-start justify-between gap-x-3 gap-y-1">
      <h3 class="min-w-0 flex-1 pt-2 text-xs font-bold uppercase tracking-wide text-slate-600">Branchen</h3>
      <button v-if="!filter.allCategoriesActive" class="min-h-8 shrink-0 cursor-pointer rounded-md px-2 text-xs font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="filter.resetCategories()">
        Filter aufheben
      </button>
    </div>
    <div class="space-y-1">
      <IndustryToggle
        v-for="industry in industries"
        :key="industry.key"
        :label="industry.label"
        :color="industryColors[industry.key]"
        :active="filter.activeCategories.includes(industry.key)"
        :count="combinedCount(industry.key)"
        :count-description="countDescription(industry.key)"
        :locked="filter.activeCategories.length === 1 && filter.activeCategories.includes(industry.key)"
        @toggle="filter.toggleCategory(industry.key)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IndustryKey } from '~/utils/industries'
import { industries, industryColors } from '~/utils/industries'

const filter = useFilterStore()
const analytics = useAnalyticsStore()
const osm = useOsmViewportStore()

function combinedCount(category: IndustryKey) {
  return (analytics.categoryCounts[category] || 0) + (osm.data?.meta.canonical_facets?.[category] || 0)
}

function countDescription(category: IndustryKey) {
  return `${analytics.categoryCounts[category] || 0} Stadtplaner · ${osm.data?.meta.canonical_facets?.[category] || 0} OpenStreetMap im Ausschnitt`
}
</script>
