<template>
  <div>
    <h2 class="mb-2 text-[12px] font-semibold uppercase text-[#3f4448]">Branchen</h2>
    <div class="space-y-[6px]">
      <IndustryToggle label="alle abwählen" color="#111111" :active="filter.allCategoriesActive" @toggle="filter.toggleAll()" />
      <IndustryToggle
        v-for="industry in industries"
        :key="industry.key"
        :label="industry.label"
        :color="industryColors[industry.key]"
        :active="filter.activeCategories.includes(industry.key)"
        @toggle="filter.toggleCategory(industry.key)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { industries, industryColors } from '~/utils/industries'

const filter = useFilterStore()
</script>

