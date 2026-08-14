<template>
  <div class="pointer-events-auto flex w-11 flex-col items-stretch gap-2" role="group" aria-label="Kartensteuerung" @click.stop>
    <MapControls @zoom-in="$emit('zoomIn')" @zoom-out="$emit('zoomOut')" @reset="$emit('reset')" />
    <MapLayerControl />
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  zoomIn: []
  zoomOut: []
  reset: []
}>()
</script>
