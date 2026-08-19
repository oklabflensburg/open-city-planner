<template>
  <GisFilterToggleRow
    :model-value="active"
    :label="label"
    :active-color="color"
    :count="count"
    :description="countDescription"
    :locked="locked"
    @update:model-value="$emit('toggle')"
  />
</template>

<script setup lang="ts">
defineProps<{ label: string; color: string; active: boolean; count?: number; countDescription?: string; locked?: boolean }>()
defineEmits<{ toggle: [] }>()
</script>
