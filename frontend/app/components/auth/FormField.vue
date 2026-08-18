<template>
  <label class="grid min-w-0 gap-1.5 text-sm font-semibold text-[var(--c-text)]">
    <span>{{ label }}</span>
    <input
      :id="id"
      class="min-h-11 w-full min-w-0 cursor-text rounded-xl border border-slate-300 border-[var(--c-border-strong)] bg-white px-3 text-sm font-normal text-[var(--c-text)] outline-none transition focus:border-[var(--c-primary-600)] focus:ring-2 focus:ring-[var(--c-secondary-500)]/20 disabled:cursor-not-allowed disabled:bg-[var(--c-surface-muted)]"
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
