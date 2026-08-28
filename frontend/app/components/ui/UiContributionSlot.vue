<template>
  <div v-if="contributions.length" :data-ui-slot="slot">
    <component
      :is="resolveUiComponent(contribution.component)"
      v-for="contribution in contributions"
      :key="contribution.id"
      v-bind="{ ...contribution.props, ...componentProps }"
      :data-ui-contribution="contribution.id"
      :aria-label="'accessibleLabel' in contribution ? contribution.accessibleLabel : undefined"
    />
  </div>
</template>

<script setup lang="ts">
import type { ComponentUiSlotId } from '#frontend-module-sdk'
import { resolveComponent } from 'vue'

const props = defineProps<{
  slot: ComponentUiSlotId
  componentProps?: Readonly<Record<string, unknown>>
}>()
const contributions = useUiContributions(props.slot)
const componentProps = computed(() => props.componentProps || {})

function resolveUiComponent(name: string) {
  return resolveComponent(name)
}
</script>
