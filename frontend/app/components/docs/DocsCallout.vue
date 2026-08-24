<template>
  <aside class="my-5 rounded-xl border p-4 sm:p-5" :class="styles" :aria-label="title">
    <div class="flex gap-3">
      <component :is="icon" class="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div>
        <p class="font-bold">{{ title }}</p>
        <p class="mt-1 text-sm leading-6">{{ text }}</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { CircleAlert, Info, Lightbulb, ShieldAlert } from '@lucide/vue'

const props = defineProps<{
  variant: 'info' | 'tip' | 'warning' | 'important'
  title: string
  text: string
}>()

const icon = computed(() => ({ info: Info, tip: Lightbulb, warning: CircleAlert, important: ShieldAlert })[props.variant])
const styles = computed(() => ({
  info: 'border-sky-200 bg-sky-50 text-sky-950',
  tip: 'border-emerald-200 bg-emerald-50 text-emerald-950',
  warning: 'border-amber-200 bg-amber-50 text-amber-950',
  important: 'border-rose-200 bg-rose-50 text-rose-950'
})[props.variant])
</script>
