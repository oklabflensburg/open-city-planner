<template>
  <div class="space-y-5">
    <MultiSelectFilterGroup v-model="filter.occupancyStatuses" title="Status" :options="occupancyOptions" :columns="2" />
    <MultiSelectFilterGroup v-model="filter.businessStructures" title="Betriebsform" :options="structureOptions" :columns="2" />
  </div>
</template>

<script setup lang="ts">
import { BUSINESS_STRUCTURE_OPTIONS, OCCUPANCY_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
const occupancyOptions = OCCUPANCY_OPTIONS.map(item => ({ ...item, description: `Status: ${item.label}` }))
const structureOptions = BUSINESS_STRUCTURE_OPTIONS.map(item => ({ ...item, description: `Betriebsform: ${item.label}` }))
</script>
