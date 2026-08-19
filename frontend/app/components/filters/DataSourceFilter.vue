<template>
  <MultiSelectFilterGroup
    :model-value="filter.selectedSources"
    title="Datenquellen"
    :options="DATA_SOURCE_OPTIONS"
    variant="switches"
    allow-empty
    @update:model-value="filter.setSources"
  />
</template>

<script setup lang="ts">
import { DATA_SOURCE_OPTIONS } from '~/utils/gisFilters'

const filter = useFilterStore()
</script>
