<template>
  <section class="overview-shell relative h-[calc(100dvh-64px)] min-h-[620px] bg-[#f4f4f4] text-[#2f3337] lg:grid lg:gap-3 lg:p-3">
    <div class="hidden min-h-0 lg:block">
      <LeftSidebar />
    </div>

    <section class="absolute inset-0 p-2 lg:relative lg:inset-auto lg:min-h-0 lg:p-0">
      <MapCanvas />
    </section>

    <div class="hidden min-h-0 lg:block">
      <RightSidebar />
    </div>

    <div class="fixed left-3 top-[76px] z-30 flex gap-2 lg:hidden">
      <IconButton label="Filter öffnen" @click="mapStore.filterDrawerOpen = true">
        <span class="relative"><ListFilter class="size-5" /><span v-if="activeFilterCount" class="absolute -right-3 -top-3 grid size-5 place-items-center rounded-full bg-[#154d73] text-[10px] font-bold text-white">{{ activeFilterCount }}</span></span>
      </IconButton>
    </div>
    <div class="fixed bottom-3 right-3 z-30 lg:hidden">
      <IconButton label="Analyse öffnen" @click="mapStore.analysisDrawerOpen = true"><BarChart3 class="size-5" /></IconButton>
    </div>

    <Drawer :open="mapStore.filterDrawerOpen" @close="mapStore.filterDrawerOpen = false">
      <div class="h-full overflow-y-auto bg-slate-50 p-4">
        <div class="mb-3 flex justify-end">
          <button class="rounded-md p-2" type="button" aria-label="Filter schließen" @click="mapStore.filterDrawerOpen = false">
            <X class="size-5" />
          </button>
        </div>
        <LeftSidebar />
      </div>
    </Drawer>

    <Drawer :open="mapStore.analysisDrawerOpen" side="bottom" @close="mapStore.analysisDrawerOpen = false">
      <div class="max-h-[72vh] overflow-y-auto p-3">
        <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-[#cfd3d6]" />
        <RightSidebar />
      </div>
    </Drawer>
  </section>
</template>

<script setup lang="ts">
import { BarChart3, ListFilter, X } from 'lucide-vue-next'

const mapStore = useMapStore()
const filterStore = useFilterStore()
const analyticsStore = useAnalyticsStore()
const activeFilterCount = computed(() => (
  (filterStore.selectedSize !== 'M' ? 1 : 0)
  + (filterStore.selectedFloor !== 'EG' ? 1 : 0)
  + (filterStore.allCategoriesActive ? 0 : 1)
))

let analyticsTimer: ReturnType<typeof setTimeout> | undefined
onMounted(() => analyticsStore.load())
watch(
  () => [filterStore.selectedSize, filterStore.selectedFloor, ...filterStore.activeCategories],
  () => {
    clearTimeout(analyticsTimer)
    analyticsTimer = setTimeout(() => analyticsStore.load(), 180)
  }
)
onBeforeUnmount(() => clearTimeout(analyticsTimer))
</script>

<style scoped>
@media (min-width: 1024px) {
  .overview-shell { grid-template-columns: 260px minmax(0, 1fr) 300px; }
}

@media (min-width: 1440px) {
  .overview-shell { grid-template-columns: 280px minmax(600px, 1fr) 320px; }
}
</style>
