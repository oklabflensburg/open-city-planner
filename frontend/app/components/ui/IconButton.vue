<template>
  <button
    class="grid min-h-11 min-w-11 cursor-pointer place-items-center rounded-xl border border-[var(--c-border)] bg-white text-[var(--c-primary-800)] shadow-[var(--shadow-card)] transition hover:bg-[var(--c-surface)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--c-primary-600)] disabled:cursor-not-allowed disabled:opacity-50 lg:min-h-[36px] lg:min-w-[36px]"
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
