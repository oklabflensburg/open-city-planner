<template>
  <button
    class="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--c-primary-600)] disabled:cursor-not-allowed disabled:opacity-50"
    :class="[variantClass, { 'border-[var(--c-primary-700)] bg-[var(--c-surface-muted)] text-[var(--c-primary-800)]': active }]"
    :type="type"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  active?: boolean
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  type?: 'button' | 'submit' | 'reset'
}>(), { variant: 'secondary', type: 'button' })

const variantClass = computed(() => ({
  primary: 'border border-[var(--c-primary-700)] bg-[var(--c-primary-700)] text-white hover:bg-[var(--c-primary-800)]',
  secondary: 'border border-[var(--c-border-strong)] bg-white text-[var(--c-text)] hover:bg-[var(--c-surface)]',
  ghost: 'border border-transparent bg-transparent text-[var(--c-text)] hover:bg-[var(--c-surface-muted)]',
  danger: 'border border-rose-700 bg-rose-700 text-white hover:bg-rose-800'
})[props.variant])
</script>
