<template>
  <span
    class="inline-flex min-h-8 items-center gap-2 rounded-full border px-3 py-1 text-sm font-bold"
    :style="{ borderColor: color, color, backgroundColor: colorWithAlpha(color, 0.1) }"
  >
    <span class="size-2.5 shrink-0 rounded-full" :style="{ backgroundColor: color }" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { colorWithAlpha, getIndustryColor, getIndustryLabel } from '~/utils/industries'

const props = defineProps<{ category: string | null | undefined }>()
const color = computed(() => getIndustryColor(props.category))
const label = computed(() => getIndustryLabel(props.category))
</script>
