<template>
  <button
    class="flex min-h-11 w-full cursor-pointer items-start gap-2 rounded-lg px-1.5 py-2 text-left text-xs text-slate-600 transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] lg:min-h-9"
    type="button"
    :aria-pressed="active"
    role="checkbox"
    :aria-checked="active"
    @click="$emit('toggle')"
  >
    <span class="relative mt-0.5 h-[16px] w-[28px] shrink-0 rounded-full border border-black/10" :style="{ backgroundColor: active ? color : '#a7aaad' }">
      <span class="absolute top-[2px] h-[10px] w-[10px] rounded-full bg-white shadow-sm transition-all" :class="active ? 'left-[14px]' : 'left-[2px]'" />
    </span>
    <span class="min-w-0 flex-1 whitespace-normal leading-4 [overflow-wrap:anywhere]">{{ label }}</span>
    <span v-if="count !== undefined" class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] tabular-nums text-slate-600">{{ count }}</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{ label: string; color: string; active: boolean; count?: number }>()
defineEmits<{ toggle: [] }>()
</script>
