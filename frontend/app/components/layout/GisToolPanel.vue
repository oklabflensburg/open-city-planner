<template>
  <aside
    ref="panel"
    class="gis-tool-panel flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-[var(--radius-panel)] border border-slate-200 bg-white shadow-[var(--shadow-card)]"
    :aria-label="title"
    data-gis-tool-panel
    @keydown="handleKeydown"
  >
    <header class="flex min-h-16 shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4">
      <h2 class="min-w-0 truncate text-base font-bold text-slate-950">{{ title }}</h2>
      <button ref="closeButton" class="grid size-11 shrink-0 cursor-pointer place-items-center rounded-xl hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" :aria-label="closeLabel" @click="$emit('close')">
        <X class="size-5" aria-hidden="true" />
      </button>
    </header>
    <div ref="scroller" class="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain bg-[var(--c-surface)] p-3" data-gis-tool-panel-scroll>
      <slot />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { X } from '@lucide/vue'

const props = defineProps<{ title: string, closeLabel: string, contentKey: string }>()
const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
let returnFocusTo: HTMLElement | null = null

onMounted(() => {
  returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null
  nextTick(() => closeButton.value?.focus({ preventScroll: true }))
})

watch(() => props.contentKey, async () => {
  await nextTick()
  scroller.value?.scrollTo({ top: 0 })
})

onBeforeUnmount(() => returnFocusTo?.focus({ preventScroll: true }))

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    event.preventDefault()
    emit('close')
  }
}
</script>
