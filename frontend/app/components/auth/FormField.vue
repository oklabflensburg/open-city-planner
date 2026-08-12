<template>
  <label class="grid min-w-0 gap-1 text-sm font-semibold text-[#30363a]">
    <span>{{ label }}</span>
    <input
      class="min-h-11 w-full min-w-0 rounded-md border border-[#d7dddf] px-3 text-sm font-normal text-[#202427] outline-none transition focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/20 disabled:bg-[#f4f6f6]"
      :type="type"
      :autocomplete="autocomplete"
      :value="modelValue"
      :required="required"
      :disabled="disabled"
      :aria-describedby="error ? `${id}-error` : undefined"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    >
    <span v-if="error" :id="`${id}-error`" class="text-xs font-semibold text-red-700">{{ error }}</span>
  </label>
</template>

<script setup lang="ts">
defineProps<{
  id: string
  label: string
  modelValue: string
  type?: string
  autocomplete?: string
  required?: boolean
  disabled?: boolean
  error?: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>
