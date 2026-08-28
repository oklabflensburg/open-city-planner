<template>
  <PolygonStatistics v-if="selectedMapEntity?.type === 'polygon'" :embedded="embedded" />
  <OsmFeatureSidebar v-else-if="selectedMapEntity?.type === 'osm'" :embedded="embedded" />
  <AnalysisAreaCard v-else-if="analysisAreas.selectedArea" :embedded="embedded" />
</template>

<script setup lang="ts">
withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const { selectedMapEntity } = useMapSelection()
const analysisAreas = useAnalysisAreasStore()
</script>
