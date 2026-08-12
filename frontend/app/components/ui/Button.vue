<template>
  <button
    class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[10px] border border-[#dddddd] bg-white px-3 text-xs font-semibold text-[#34383c] transition hover:bg-[#f6f6f6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50 md:min-h-9"
    :class="{ 'border-[#154d73] bg-[#edf4f8] text-[#154d73]': active }"
    type="button"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps<{ active?: boolean }>()
</script>

