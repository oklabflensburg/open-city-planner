<template>
  <div>
    <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Branchen</h3>
    <div class="space-y-1">
      <IndustryToggle :label="filter.allCategoriesActive ? 'Alle abwählen' : 'Alle auswählen'" color="#334155" :active="filter.allCategoriesActive" @toggle="filter.toggleAll()" />
      <IndustryToggle
        v-for="industry in industries"
        :key="industry.key"
        :label="industry.label"
        :color="industryColors[industry.key]"
        :active="filter.activeCategories.includes(industry.key)"
        :count="analytics.categoryCounts[industry.key]"
        @toggle="filter.toggleCategory(industry.key)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { industries, industryColors } from '~/utils/industries'

const filter = useFilterStore()
const analytics = useAnalyticsStore()
</script>
