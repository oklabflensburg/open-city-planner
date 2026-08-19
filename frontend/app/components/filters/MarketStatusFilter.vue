<template>
  <div class="space-y-5">
    <MultiSelectFilterGroup :model-value="filter.occupancyStatuses" title="Status" :options="occupancyOptions" variant="switches" @update:model-value="filter.setOccupancyStatuses" />
    <MultiSelectFilterGroup :model-value="filter.businessStructures" title="Betriebsform" :options="structureOptions" variant="switches" @update:model-value="filter.setBusinessStructures" />
  </div>
</template>

<script setup lang="ts">
import { BUSINESS_STRUCTURE_OPTIONS, OCCUPANCY_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
const occupancyOptions = OCCUPANCY_OPTIONS.map(item => ({
  ...item,
  activeColor: item.color,
  description: `Status: ${item.label}`
}))
const structureOptions = BUSINESS_STRUCTURE_OPTIONS.map(item => ({ ...item, description: `Betriebsform: ${item.label}` }))
</script>
