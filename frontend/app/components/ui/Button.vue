<template>
  <button
    class="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50"
    :class="[variantClass, { 'border-[#154d73] bg-[#edf4f8] text-[#154d73]': active }]"
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
  primary: 'border border-[#154d73] bg-[#154d73] text-white hover:bg-[#0f3f61]',
  secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
  ghost: 'border border-transparent bg-transparent text-slate-700 hover:bg-slate-100',
  danger: 'border border-rose-700 bg-rose-700 text-white hover:bg-rose-800'
})[props.variant])
</script>
