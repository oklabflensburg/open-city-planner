<template>
  <section aria-label="Kartenlegende">
    <h3 class="text-xs font-bold uppercase tracking-wide text-slate-500">Legende</h3>
    <p class="mt-2 text-xs font-bold text-slate-700">{{ title }}</p>
    <ul class="mt-2 grid gap-2 text-xs text-slate-700">
      <li v-for="item in items" :key="item.label" class="flex min-w-0 items-start gap-2">
        <span class="mt-0.5 size-3 shrink-0 rounded-full border border-black/10" :style="{ backgroundColor: item.color }" aria-hidden="true" />
        <span class="min-w-0 whitespace-normal break-words leading-4">{{ item.label }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { industries } from '~/utils/industries'
import { businessLegend, mapThemes, occupancyLegend, sizeLegend, type MapTheme } from '~/utils/mapThemes'

const props = defineProps<{ theme: MapTheme }>()
const title = computed(() => mapThemes.find(item => item.key === props.theme)?.label || 'Legende')
const items = computed(() => {
  if (props.theme === 'occupancy') return occupancyLegend
  if (props.theme === 'size') return sizeLegend
  if (props.theme === 'business') return businessLegend
  return industries.map(item => ({ value: item.key, label: item.label, color: item.color }))
})
</script>
