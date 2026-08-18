<template>
  <button
    class="group flex min-h-[44px] w-full min-w-0 cursor-pointer items-start gap-[6px] rounded-lg px-[2px] py-[8px] text-left text-xs text-slate-700 transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50"
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="accessibleLabel"
    :aria-describedby="description ? descriptionId : undefined"
    :disabled="disabled"
    @click="$emit('update:modelValue', !modelValue)"
  >
    <span
      class="relative mt-[3px] h-[18px] w-[34px] shrink-0 rounded-full transition-colors"
      :class="modelValue ? (activeColor ? '' : 'bg-[#0b8190]') : 'bg-slate-300'"
      :style="modelValue && activeColor ? { backgroundColor: activeColor } : undefined"
      aria-hidden="true"
    >
      <span
        class="absolute left-[2px] top-[2px] size-[14px] rounded-full bg-white shadow-sm transition-transform"
        :class="modelValue ? 'translate-x-[16px]' : 'translate-x-0'"
      />
    </span>
    <span
      v-if="color || colorClass"
      class="mt-[6px] size-[10px] shrink-0"
      :class="[colorClass, squareIndicator ? 'rounded-sm' : 'rounded-full']"
      :style="color ? { backgroundColor: color, boxShadow: colorBorder ? `inset 0 0 0 1px ${colorBorder}` : undefined } : undefined"
      aria-hidden="true"
    />
    <span class="min-w-0 flex-1 whitespace-normal leading-5 [overflow-wrap:break-word] [word-break:normal]">{{ label }}</span>
    <span
      v-if="count !== undefined"
      class="min-w-[26px] shrink-0 rounded-full bg-slate-100 px-[6px] py-[2px] text-center text-[10px] tabular-nums text-slate-600"
      aria-hidden="true"
    >{{ formattedCount }}</span>
    <span v-if="description" :id="descriptionId" class="sr-only">{{ description }}</span>
  </button>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  label: string
  modelValue: boolean
  count?: number
  color?: string
  colorClass?: string
  activeColor?: string
  ariaLabel?: string
  colorBorder?: string
  squareIndicator?: boolean
  disabled?: boolean
  description?: string
  context?: string
}>(), {
  count: undefined,
  color: undefined,
  colorClass: undefined,
  activeColor: undefined,
  ariaLabel: undefined,
  colorBorder: undefined,
  squareIndicator: false,
  disabled: false,
  description: undefined,
  context: undefined
})

defineEmits<{ 'update:modelValue': [value: boolean] }>()

const descriptionId = useId()
const formattedCount = computed(() => props.count?.toLocaleString('de-DE'))
const accessibleLabel = computed(() => {
  const prefix = props.ariaLabel || (props.context ? `${props.context} ${props.label}` : props.label)
  const state = props.modelValue ? 'eingeschaltet' : 'ausgeschaltet'
  const count = props.count === undefined ? '' : `, ${formattedCount.value} Treffer`
  return `${prefix}: ${state}${count}`
})
</script>
