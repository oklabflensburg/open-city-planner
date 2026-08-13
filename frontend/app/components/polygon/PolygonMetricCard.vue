<template>
  <div class="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_4px_rgba(15,23,42,0.04)]">
    <div class="flex items-center gap-2 text-sm font-semibold text-slate-500">
      <component :is="icon" v-if="icon" class="size-4 shrink-0" aria-hidden="true" />
      <span>{{ label }}</span>
    </div>
    <p class="mt-2 break-words text-lg font-bold text-slate-950">{{ value }}</p>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
defineProps<{ label: string, value: string, icon?: Component }>()
</script>
