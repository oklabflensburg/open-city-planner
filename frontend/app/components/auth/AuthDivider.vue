<template>
  <div class="flex items-center gap-3">
    <div class="h-px flex-1 bg-slate-200" />
    <span class="text-xs font-semibold text-slate-500">{{ label }}</span>
    <div class="h-px flex-1 bg-slate-200" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
}>()
</script>
