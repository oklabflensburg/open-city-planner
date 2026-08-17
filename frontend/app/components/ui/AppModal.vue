<template>
  <Teleport to="body">
    <Transition name="app-modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-slate-950/40 p-4 [padding-bottom:max(1rem,env(safe-area-inset-bottom))] [padding-top:max(1rem,env(safe-area-inset-top))] backdrop-blur-[1px]"
        data-app-modal-root
        @click.self="requestOverlayClose"
      >
        <section
          ref="panel"
          class="flex max-h-[calc(100dvh-2rem)] w-full min-w-0 max-w-full flex-col overflow-hidden rounded-[var(--radius-panel)] border border-[var(--c-border)] bg-white shadow-[var(--shadow-floating)] outline-none"
          :class="sizeClass"
          :role="role"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="modalDescribedBy"
          tabindex="-1"
          data-app-modal
          @keydown="handleKeydown"
        >
          <header class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-6 sm:py-5">
            <div class="min-w-0">
              <h2 :id="titleId" class="text-lg font-bold text-slate-950 sm:text-xl">{{ title }}</h2>
              <p v-if="description" :id="descriptionId" class="mt-1 text-sm leading-6 text-slate-600">{{ description }}</p>
            </div>
            <button
              v-if="showClose"
              class="grid size-11 shrink-0 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-wait disabled:opacity-50"
              type="button"
              :disabled="busy"
              :aria-label="`${title} schließen`"
              @click="requestClose"
            >
              <X class="size-5" aria-hidden="true" />
            </button>
          </header>

          <div class="min-h-0 min-w-0 max-w-full flex-1 overflow-y-auto overscroll-contain px-5 py-5 sm:px-6 sm:py-6">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="shrink-0 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script lang="ts">
let modalLockCount = 0

function lockBody() {
  modalLockCount += 1
  document.body.classList.add('modal-open')
}

function unlockBody() {
  modalLockCount = Math.max(0, modalLockCount - 1)
  if (modalLockCount === 0) document.body.classList.remove('modal-open')
}
</script>

<script setup lang="ts">
import { X } from 'lucide-vue-next'

type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  describedBy?: string
  size?: ModalSize
  role?: 'dialog' | 'alertdialog'
  busy?: boolean
  closeOnOverlay?: boolean
  closeOnEscape?: boolean
  showClose?: boolean
}>(), {
  size: 'md',
  role: 'dialog',
  busy: false,
  closeOnOverlay: true,
  closeOnEscape: true,
  showClose: true
})

const emit = defineEmits<{
  'update:open': [open: boolean]
  close: []
}>()

const panel = ref<HTMLElement | null>(null)
const instanceId = useId()
const titleId = `app-modal-title-${instanceId}`
const descriptionId = `app-modal-description-${instanceId}`
let returnFocusTo: HTMLElement | null = null
let bodyLocked = false

const sizeClass = computed(() => ({
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-lg',
  lg: 'sm:max-w-2xl',
  xl: 'sm:max-w-4xl'
})[props.size])
const modalDescribedBy = computed(() => [props.description ? descriptionId : '', props.describedBy].filter(Boolean).join(' ') || undefined)

watch(() => props.open, async (open) => {
  if (!import.meta.client) return
  if (open) {
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null
    if (!bodyLocked) {
      lockBody()
      bodyLocked = true
    }
    await nextTick()
    const initialFocus = panel.value?.querySelector<HTMLElement>('[data-autofocus]:not([disabled])')
    ;(initialFocus || panel.value)?.focus()
    return
  }
  releaseOpenState()
}, { immediate: true })

onBeforeUnmount(releaseOpenState)

function releaseOpenState() {
  if (!import.meta.client) return
  if (bodyLocked) {
    unlockBody()
    bodyLocked = false
  }
  returnFocusTo?.focus()
  returnFocusTo = null
}

function requestClose() {
  if (props.busy) return
  emit('update:open', false)
  emit('close')
}

function requestOverlayClose() {
  if (props.closeOnOverlay) requestClose()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.closeOnEscape) {
    event.preventDefault()
    requestClose()
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
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
</script>

<style scoped>
.app-modal-enter-active,
.app-modal-leave-active {
  transition: opacity 160ms ease;
}

.app-modal-enter-active [data-app-modal],
.app-modal-leave-active [data-app-modal] {
  transition: transform 180ms ease, opacity 160ms ease;
}

.app-modal-enter-from,
.app-modal-leave-to {
  opacity: 0;
}

.app-modal-enter-from [data-app-modal],
.app-modal-leave-to [data-app-modal] {
  opacity: 0;
  transform: translateY(1rem) scale(0.985);
}

@media (prefers-reduced-motion: reduce) {
  .app-modal-enter-active,
  .app-modal-leave-active,
  .app-modal-enter-active [data-app-modal],
  .app-modal-leave-active [data-app-modal] {
    transition: none;
  }
}
</style>
