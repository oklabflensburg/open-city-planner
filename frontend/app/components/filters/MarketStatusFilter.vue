<template>
  <div class="space-y-5">
    <MultiSelectFilterGroup v-model="filter.occupancyStatuses" title="Status" :options="occupancyOptions" variant="switches" />
    <MultiSelectFilterGroup v-model="filter.businessStructures" title="Betriebsform" :options="structureOptions" variant="switches" />
  </div>
</template>

<script setup lang="ts">
import { BUSINESS_STRUCTURE_OPTIONS, OCCUPANCY_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
const occupancyColors: Record<(typeof OCCUPANCY_OPTIONS)[number]['value'], string> = {
  OCCUPIED: '#10b981',
  VACANT: '#f43f5e',
  UNKNOWN: '#94a3b8'
}
const occupancyOptions = OCCUPANCY_OPTIONS.map(item => ({
  ...item,
  activeColor: occupancyColors[item.value],
  description: `Status: ${item.label}`
}))
const structureOptions = BUSINESS_STRUCTURE_OPTIONS.map(item => ({ ...item, description: `Betriebsform: ${item.label}` }))
</script>
