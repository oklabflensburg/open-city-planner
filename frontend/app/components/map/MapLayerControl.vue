<template>
  <div ref="control" class="relative h-11 w-11">
    <button
      class="grid h-11 w-11 cursor-pointer place-items-center rounded-xl border shadow-sm transition-colors hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
      :class="open ? 'border-[#154d73] bg-[#edf4f8] text-[#154d73]' : 'border-slate-200 bg-white text-slate-600'"
      type="button"
      aria-label="Kartenlayer"
      :aria-expanded="open"
      aria-controls="map-layer-menu"
      title="Kartenlayer"
      @click.stop="open = !open"
    >
      <Layers class="size-5" aria-hidden="true" />
    </button>
    <div v-if="open" id="map-layer-menu" class="absolute bottom-0 right-[calc(100%+0.5rem)] w-52 rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-lg">
      <GisFilterToggleRow v-model="mapStore.polygonsVisible" label="Verkaufsflächen" aria-label="Verkaufsflächen anzeigen" />
      <fieldset class="mt-2 border-t border-slate-200 pt-2">
        <legend class="px-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Kartendarstellung</legend>
        <label v-for="theme in mapThemes" :key="theme.key" class="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-1 hover:bg-slate-50">
          <input v-model="mapStore.thematicStyle" class="accent-[#154d73]" type="radio" name="map-theme" :value="theme.key">
          {{ theme.label }}
        </label>
      </fieldset>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Layers } from 'lucide-vue-next'
import { mapThemes } from '~/utils/mapThemes'

const open = ref(false)
const mapStore = useMapStore()
const control = ref<HTMLElement | null>(null)

onMounted(() => {
  window.addEventListener('keydown', closeOnEscape)
  window.addEventListener('click', closeOnOutsideClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', closeOnEscape)
  window.removeEventListener('click', closeOnOutsideClick)
})

function closeOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}

function closeOnOutsideClick(event: MouseEvent) {
  if (open.value && !control.value?.contains(event.target as Node)) open.value = false
}
</script>
