<template>
  <PolygonStatistics v-if="selectedMapEntity?.type === 'polygon'" :embedded="embedded" />
  <OsmFeatureSidebar v-else-if="selectedMapEntity?.type === 'osm'" :embedded="embedded" />
  <UiContributionSlot v-else slot="map.selection" :component-props="{ embedded }" />
</template>

<script setup lang="ts">
withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const { selectedMapEntity } = useMapSelection()
</script>
