<template>
  <header class="space-y-4">
    <PageBreadcrumbs v-if="breadcrumbs?.length" :items="breadcrumbs" />
    <div class="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0 max-w-3xl">
        <div v-if="$slots.badge || eyebrow" class="mb-3">
          <slot name="badge">
            <p class="text-xs font-bold uppercase tracking-[0.12em] text-[#154d73]">{{ eyebrow }}</p>
          </slot>
        </div>
        <h1 class="break-words text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">{{ title }}</h1>
        <p v-if="description" class="mt-4 max-w-3xl text-base leading-7 text-slate-600 sm:text-lg sm:leading-8">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 flex-wrap gap-3 sm:pt-1">
        <slot name="actions" />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import type { BreadcrumbItem } from './PageBreadcrumbs.vue'

defineProps<{
  title: string
  description?: string
  eyebrow?: string
  breadcrumbs?: BreadcrumbItem[]
}>()
</script>
