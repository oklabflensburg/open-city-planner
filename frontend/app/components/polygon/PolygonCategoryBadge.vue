<template>
  <span
    class="inline-flex min-h-8 max-w-full min-w-0 items-center gap-2 whitespace-normal rounded-full border px-3 py-1 text-sm font-bold"
    :style="{ borderColor: color, color, backgroundColor: colorWithAlpha(color, 0.1) }"
  >
    <span class="size-2.5 shrink-0 rounded-full" :style="{ backgroundColor: color }" aria-hidden="true" />
    <span class="min-w-0 [overflow-wrap:break-word]">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { colorWithAlpha, getIndustryColor, getIndustryLabel } from '~/utils/industries'

const props = defineProps<{ category: string | null | undefined }>()
const color = computed(() => getIndustryColor(props.category))
const label = computed(() => getIndustryLabel(props.category))
</script>
