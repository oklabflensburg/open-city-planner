<template>
  <MultiSelectFilterGroup
    v-model="filter.selectedSources"
    title="Datenquellen"
    :options="DATA_SOURCE_OPTIONS"
    :columns="2"
  />
</template>

<script setup lang="ts">
import { DATA_SOURCE_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
