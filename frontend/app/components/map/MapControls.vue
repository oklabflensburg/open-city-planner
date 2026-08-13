<template>
  <div class="pointer-events-auto flex flex-col overflow-hidden rounded-[10px] border border-[#e5e5e5] bg-white shadow-[0_1px_8px_rgba(20,24,28,0.12)]">
    <button class="grid min-h-11 min-w-11 place-items-center hover:bg-[#f5f5f5] lg:min-h-[34px] lg:min-w-[34px]" type="button" aria-label="Vergrößern" @click="$emit('zoomIn')">
      <Plus class="size-4" />
    </button>
    <button class="grid min-h-11 min-w-11 place-items-center border-t border-[#ececec] hover:bg-[#f5f5f5] lg:min-h-[34px] lg:min-w-[34px]" type="button" aria-label="Verkleinern" @click="$emit('zoomOut')">
      <Minus class="size-4" />
    </button>
    <button class="grid min-h-11 min-w-11 place-items-center border-t border-[#ececec] hover:bg-[#f5f5f5] lg:min-h-[34px] lg:min-w-[34px]" type="button" aria-label="Ansicht zurücksetzen" @click="$emit('reset')">
      <RotateCcw class="size-4" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { Minus, Plus, RotateCcw } from 'lucide-vue-next'

defineEmits<{ zoomIn: []; zoomOut: []; reset: [] }>()
</script>
