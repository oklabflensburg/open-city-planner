<template>
  <button
    class="grid min-h-11 min-w-11 place-items-center rounded-[10px] border border-[#e5e5e5] bg-white text-[#303438] shadow-[0_1px_8px_rgba(20,24,28,0.08)] transition hover:bg-[#f7f7f7] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] md:min-h-[34px] md:min-w-[34px]"
    :aria-label="label"
    :title="label"
    type="button"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps<{ label: string }>()
</script>

