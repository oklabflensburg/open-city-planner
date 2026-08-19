<template>
  <MultiSelectFilterGroup :model-value="filter.selectedFloors" title="Etagen" :options="FLOOR_OPTIONS" :columns="3" @update:model-value="filter.setFloors" />
</template>

<script setup lang="ts">
import { FLOOR_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
