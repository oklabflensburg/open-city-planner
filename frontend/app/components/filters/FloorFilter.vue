<template>
  <MultiSelectFilterGroup v-model="filter.selectedFloors" title="Etagen" :options="FLOOR_OPTIONS" :columns="3" />
</template>

<script setup lang="ts">
import { FLOOR_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
