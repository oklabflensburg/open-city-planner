<template>
  <div class="pointer-events-auto">
    <button
      class="grid min-h-11 min-w-11 place-items-center rounded-[10px] border border-[#e5e5e5] bg-white shadow-[0_1px_8px_rgba(20,24,28,0.12)] hover:bg-[#f5f5f5] md:min-h-[34px] md:min-w-[34px]"
      type="button"
      aria-label="Kartenlayer"
      title="Kartenlayer"
      @click="open = !open"
    >
      <Layers class="size-5 text-[#7c8389]" />
    </button>
    <div v-if="open" class="mt-2 w-48 rounded-[12px] border border-[#e7e7e7] bg-white p-3 text-[12px] shadow-[0_6px_24px_rgba(20,24,28,0.12)]">
      <label class="flex items-center gap-2">
        <input v-model="polygonsVisible" class="accent-[#154d73]" type="checkbox" @change="$emit('togglePolygons', polygonsVisible)" />
        Verkaufsflächen
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Layers } from 'lucide-vue-next'

defineEmits<{ togglePolygons: [visible: boolean] }>()

const open = ref(false)
const polygonsVisible = ref(true)
</script>
