<template>
  <span class="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold" :class="styles"><slot /></span>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{ tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }>(), { tone: 'neutral' })
const styles = computed(() => ({
  neutral: 'border-slate-200 bg-slate-100 text-slate-700',
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  danger: 'border-rose-200 bg-rose-50 text-rose-800'
})[props.tone])
</script>
