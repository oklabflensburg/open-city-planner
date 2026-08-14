<template>
  <div>
    <p v-if="vacant" class="mb-2 text-xs leading-5 text-amber-800">Ist diese Fläche nicht mehr leer oder zeigt OSM noch eine alte Nutzung?</p>
    <button class="inline-flex min-h-11 items-center gap-2 text-xs font-bold text-[#154d73] underline" type="button" @click="open = true">
      <ExternalLink class="size-4" aria-hidden="true" /> OpenStreetMap-Daten verbessern
    </button>
    <OsmContributeDialog
      v-model:open="open"
      :latitude="latitude"
      :longitude="longitude"
      :zoom="zoom"
    />
  </div>
</template>

<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'

defineProps<{ latitude?: number, longitude?: number, zoom?: number, vacant?: boolean }>()
const open = ref(false)
</script>
