<template>
  <Teleport to="body">
    <div v-if="open" class="lg:hidden">
      <button class="fixed inset-0 z-40 cursor-pointer bg-slate-950/30" type="button" tabindex="-1" aria-label="Dialog schließen" @click="$emit('close')" />
      <aside
        ref="panel"
        class="fixed z-50 min-w-0 bg-white shadow-[0_8px_40px_rgba(0,0,0,0.18)] outline-none lg:hidden"
        :class="side === 'bottom'
          ? 'inset-x-0 bottom-0 max-h-[min(78dvh,720px)] rounded-t-[20px] pb-[env(safe-area-inset-bottom)]'
          : 'inset-y-0 left-0 w-[min(360px,94vw)] pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]'"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        tabindex="-1"
        @keydown="handleKeydown"
      >
        <slot />
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{ open: boolean; side?: 'left' | 'bottom'; label?: string }>(), {
  side: 'left',
  label: 'Dialog'
})
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
let returnFocusTo: HTMLElement | null = null

watch(() => props.open, async (open) => {
  if (!import.meta.client) return
  if (open) {
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null
    document.body.classList.add('drawer-open')
    await nextTick()
    panel.value?.focus()
  } else {
    document.body.classList.remove('drawer-open')
    returnFocusTo?.focus()
    returnFocusTo = null
  }
})

onBeforeUnmount(() => {
  if (!import.meta.client) return
  document.body.classList.remove('drawer-open')
})

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (event.key !== 'Tab' || !panel.value) return
  const focusable = [...panel.value.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
  if (!focusable.length) {
    event.preventDefault()
    panel.value.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.value)) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.value)) {
    event.preventDefault()
    first?.focus()
  }
}
</script>
