<template>
  <a
    :class="variant === 'card'
      ? 'group flex min-w-0 items-start justify-between gap-4 rounded-xl bg-slate-50 p-4 text-left hover:bg-slate-100'
      : 'inline-flex min-h-9 items-center gap-1 font-semibold text-[#154d73] underline decoration-slate-300 underline-offset-2 hover:decoration-[#154d73]'"
    :href="url"
    target="_blank"
    rel="noopener noreferrer"
    :aria-label="accessibleName"
  >
    <span v-if="variant === 'card'" class="min-w-0">
      <span class="block text-xs font-bold uppercase tracking-wide text-slate-500">{{ label }}</span>
      <span class="mt-1 block break-words font-semibold text-slate-900">{{ title }}</span>
      <span class="mt-1 block text-sm leading-5 text-slate-600">{{ description }}</span>
    </span>
    <template v-else>{{ label }}</template>
    <ExternalLink class="mt-0.5 size-4 shrink-0 text-[#154d73]" aria-hidden="true" />
  </a>
</template>

<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'

withDefaults(defineProps<{
  label: string
  title: string
  url: string
  description: string
  accessibleName: string
  variant?: 'compact' | 'card'
}>(), { variant: 'compact' })
</script>
