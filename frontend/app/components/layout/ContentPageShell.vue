<template>
  <div class="min-h-[calc(100dvh-4rem)] bg-slate-50">
    <div class="mx-auto w-full px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12" :class="widthClass">
      <PageHeader
        v-if="title"
        :title="title"
        :description="description"
        :eyebrow="eyebrow"
        :breadcrumbs="breadcrumbs"
      >
        <template v-if="$slots.badge" #badge><slot name="badge" /></template>
        <template v-if="$slots.actions" #actions><slot name="actions" /></template>
      </PageHeader>

      <div :class="title ? 'mt-8 sm:mt-10' : ''">
        <div v-if="$slots.aside" class="grid min-w-0 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div class="min-w-0"><slot /></div>
          <aside class="min-w-0"><slot name="aside" /></aside>
        </div>
        <slot v-else />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BreadcrumbItem } from './PageBreadcrumbs.vue'

const props = withDefaults(defineProps<{
  title?: string
  description?: string
  eyebrow?: string
  breadcrumbs?: BreadcrumbItem[]
  maxWidth?: 'reading' | 'content' | 'wide'
}>(), { maxWidth: 'content' })

const widthClass = computed(() => ({
  reading: 'max-w-4xl',
  content: 'max-w-6xl',
  wide: 'max-w-7xl'
})[props.maxWidth])
</script>
