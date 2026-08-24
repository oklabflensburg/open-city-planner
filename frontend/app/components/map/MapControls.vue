<template>
  <div class="flex w-11 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <button class="grid h-11 w-11 cursor-pointer place-items-center bg-white text-slate-600 transition-colors hover:bg-slate-100 focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#154d73]" type="button" aria-label="Vergrößern" @click.stop="$emit('zoomIn')">
      <Plus class="size-5" aria-hidden="true" />
    </button>
    <button class="grid h-11 w-11 cursor-pointer place-items-center border-t border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100 focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#154d73]" type="button" aria-label="Verkleinern" @click.stop="$emit('zoomOut')">
      <Minus class="size-5" aria-hidden="true" />
    </button>
    <button class="grid h-11 w-11 cursor-pointer place-items-center border-t border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100 focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#154d73]" type="button" aria-label="Ansicht zurücksetzen" @click.stop="$emit('reset')">
      <RotateCcw class="size-5" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { Minus, Plus, RotateCcw } from '@lucide/vue'

defineEmits<{ zoomIn: []; zoomOut: []; reset: [] }>()
</script>
