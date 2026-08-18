<template>
  <MultiSelectFilterGroup
    v-model="filter.selectedSources"
    title="Datenquellen"
    :options="DATA_SOURCE_OPTIONS"
    variant="switches"
  />
</template>

<script setup lang="ts">
import { DATA_SOURCE_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
