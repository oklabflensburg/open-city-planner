<template>
  <label class="grid min-w-0 gap-1.5 text-sm font-semibold text-slate-700">
    <span>{{ label }}</span>
    <input
      :id="id"
      class="min-h-11 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3 text-sm font-normal text-slate-950 outline-none transition focus:border-[#154d73] focus:ring-2 focus:ring-[#154d73]/20 disabled:bg-slate-100"
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
