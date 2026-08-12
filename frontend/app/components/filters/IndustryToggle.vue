<template>
  <button
    class="flex min-h-[22px] w-full items-center gap-2 rounded-md text-left text-[11px] text-[#555b60] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
    type="button"
    :aria-pressed="active"
    @click="$emit('toggle')"
  >
    <span class="relative h-[13px] w-[25px] rounded-full border border-black/10" :style="{ backgroundColor: active ? color : '#a7aaad' }">
      <span class="absolute top-[2px] h-[9px] w-[9px] rounded-full bg-white transition-all" :class="active ? 'left-[13px]' : 'left-[2px]'" />
    </span>
    <span class="truncate">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{ label: string; color: string; active: boolean }>()
defineEmits<{ toggle: [] }>()
</script>

