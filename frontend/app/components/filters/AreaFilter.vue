<template>
  <MultiSelectFilterGroup :model-value="filter.selectedSizes" title="Verkaufsfläche" :options="SALES_AREA_SIZE_OPTIONS" :columns="4" @update:model-value="filter.setSizes" />
</template>

<script setup lang="ts">
import { SALES_AREA_SIZE_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
