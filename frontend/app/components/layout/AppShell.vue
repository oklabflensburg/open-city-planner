<template>
  <section class="relative h-[calc(100dvh-64px)] bg-[#f4f4f4] text-[#2f3337] md:grid md:grid-cols-[220px_minmax(0,1fr)_390px] md:gap-2 md:p-2">
    <div class="hidden md:block">
      <LeftSidebar />
    </div>

    <section class="absolute inset-0 p-2 md:relative md:inset-auto md:min-h-0 md:p-0">
      <MapCanvas />
    </section>

    <div class="hidden min-h-0 md:block">
      <RightSidebar />
    </div>

    <div class="fixed left-3 top-[76px] z-30 flex gap-2 md:hidden">
      <IconButton label="Filter öffnen" @click="mapStore.filterDrawerOpen = true"><Menu class="size-5" /></IconButton>
    </div>
    <div class="fixed bottom-3 right-3 z-30 md:hidden">
      <IconButton label="Analyse öffnen" @click="mapStore.analysisDrawerOpen = true"><BarChart3 class="size-5" /></IconButton>
    </div>

    <Drawer :open="mapStore.filterDrawerOpen" @close="mapStore.filterDrawerOpen = false">
      <div class="h-full overflow-y-auto p-4">
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
import { BarChart3, Menu, X } from 'lucide-vue-next'

const mapStore = useMapStore()
</script>
