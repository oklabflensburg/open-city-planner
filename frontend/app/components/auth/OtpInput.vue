<template>
  <div>
    <label :for="id" class="mb-2 block text-sm font-semibold text-slate-800">{{ label }}</label>
    <input
      :id="id"
      ref="input"
      :value="modelValue"
      :disabled="disabled"
      :aria-describedby="describedBy"
      :aria-invalid="invalid || undefined"
      class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-center font-mono text-2xl font-bold tracking-[0.45em] text-slate-950 outline-none transition focus:border-[#154d73] focus:ring-4 focus:ring-[#154d73]/15 disabled:opacity-60 motion-reduce:transition-none"
      inputmode="numeric"
      autocomplete="one-time-code"
      pattern="[0-9]*"
      maxlength="6"
      type="text"
      @input="update"
    >
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue: string
  id?: string
  label?: string
  disabled?: boolean
  invalid?: boolean
  describedBy?: string
}>(), { id: 'mfa-code', label: 'Sechsstelliger Authenticator-Code' })

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const input = ref<HTMLInputElement | null>(null)

function update(event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value.replace(/\D/g, '').slice(0, 6)
  target.value = value
  emit('update:modelValue', value)
}

defineExpose({ focus: () => input.value?.focus() })
</script>
