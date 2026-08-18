<template>
  <fieldset class="min-w-0">
    <div class="mb-3 flex min-h-8 min-w-0 flex-wrap items-start justify-between gap-x-3 gap-y-1">
      <legend class="min-w-0 flex-1 pt-2 text-xs font-bold uppercase tracking-wide text-slate-600">{{ title }}</legend>
      <button class="min-h-8 shrink-0 rounded-md px-2 text-xs font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="toggleAll">
        {{ allSelected ? 'Alle abwählen' : 'Alle auswählen' }}
      </button>
    </div>
    <div v-if="variant === 'switches'" class="space-y-1">
      <GisFilterToggleRow
        v-for="option in options"
        :key="option.value"
        :model-value="modelValue.includes(option.value)"
        :label="option.label"
        :color-class="option.activeColor ? undefined : option.color"
        :active-color="option.activeColor"
        :description="option.description"
        :context="title"
        @update:model-value="toggle(option.value)"
      />
    </div>
    <div v-else class="grid gap-2" :class="columnsClass">
      <button
        v-for="option in options"
        :key="option.value"
        class="flex min-h-11 items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-bold text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
        :class="{ '!border-[#6f9fbd] !bg-[#edf4f8] !text-[#154d73] shadow-sm': modelValue.includes(option.value) }"
        type="button"
        :aria-pressed="modelValue.includes(option.value)"
        :aria-label="`${title} ${option.label}: ${modelValue.includes(option.value) ? 'ausgewählt' : 'nicht ausgewählt'}. ${option.description || ''}`"
        :title="option.description"
        @click="toggle(option.value)"
      >
        <span v-if="option.color" class="size-2.5 shrink-0 rounded-full" :class="option.color" aria-hidden="true" />
        {{ option.label }} <span v-if="modelValue.includes(option.value)" aria-hidden="true">✓</span>
      </button>
    </div>
  </fieldset>
</template>

<script setup lang="ts" generic="T extends string">
const props = withDefaults(defineProps<{
  title: string
  options: ReadonlyArray<{ value: T, label: string, description?: string, color?: string, activeColor?: string }>
  modelValue: T[]
  columns?: number
  variant?: 'chips' | 'switches'
}>(), { columns: 2, variant: 'chips' })
const emit = defineEmits<{ 'update:modelValue': [value: T[]] }>()
const allSelected = computed(() => props.modelValue.length === props.options.length)
const columnsClass = computed(() => ({
  'grid-cols-2': props.columns === 2,
  'grid-cols-3': props.columns === 3,
  'grid-cols-4': props.columns === 4
}))

function toggle(value: T) {
  emit('update:modelValue', props.modelValue.includes(value)
    ? props.modelValue.filter(item => item !== value)
    : [...props.modelValue, value])
}

function toggleAll() {
  emit('update:modelValue', allSelected.value ? [] : props.options.map(option => option.value))
}
</script>
