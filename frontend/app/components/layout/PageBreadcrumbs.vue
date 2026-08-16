<template>
  <nav class="flex min-w-0 flex-wrap items-center gap-2 text-sm text-slate-500" aria-label="Breadcrumb">
    <template v-for="(item, index) in items" :key="`${item.label}-${index}`">
      <ChevronRight v-if="index" class="size-4 shrink-0 text-slate-400" aria-hidden="true" />
      <NuxtLink
        v-if="item.to && index < items.length - 1"
        class="min-w-0 rounded text-slate-600 transition [overflow-wrap:anywhere] hover:text-[#154d73] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
        :to="item.to"
      >
        {{ item.label }}
      </NuxtLink>
      <span v-else class="min-w-0 [overflow-wrap:anywhere]" :aria-current="index === items.length - 1 ? 'page' : undefined">{{ item.label }}</span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'

export type BreadcrumbItem = {
  label: string
  to?: string
}

defineProps<{ items: BreadcrumbItem[] }>()
</script>
