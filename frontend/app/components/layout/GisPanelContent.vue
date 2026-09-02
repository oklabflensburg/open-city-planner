<template>
  <template v-if="mapStore.activeGisPanel === 'filter'">
    <LazyLeftSidebar embedded :compact="compact" />
    <div v-if="!compact" class="mt-3 grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <button class="min-h-11 cursor-pointer rounded-xl border border-slate-300 px-3 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="resetFilters">Zurücksetzen</button>
      <button class="min-h-11 cursor-pointer rounded-xl bg-[#154d73] px-3 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="$emit('close')">{{ resultLabel }}</button>
    </div>
  </template>
  <div v-else-if="mapStore.activeGisPanel === 'selection'" :class="compact ? 'min-h-full' : '-m-3 min-h-full bg-white p-4'">
    <MapSelectionContent embedded />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ compact?: boolean, resultLabel: string }>(), { compact: false })
defineEmits<{ close: [] }>()

const mapStore = useMapStore()
const filterStore = useFilterStore()
const osmStore = useOsmViewportStore()

function resetFilters() {
  filterStore.reset()
  osmStore.reset()
}
</script>
