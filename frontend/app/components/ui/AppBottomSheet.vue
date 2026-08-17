<template>
  <Teleport to="body">
    <Transition name="app-sheet-backdrop">
      <button
        v-if="open"
        class="fixed inset-0 z-40 cursor-default bg-slate-950/30 xl:hidden"
        type="button"
        tabindex="-1"
        aria-label="Dialog schließen"
        @click="closeOnOverlay && requestClose()"
      />
    </Transition>

    <Transition name="app-sheet-panel">
      <section
        v-if="open"
        ref="panel"
        class="app-bottom-sheet fixed inset-x-0 bottom-0 z-50 flex min-w-0 flex-col overflow-hidden rounded-t-[var(--radius-panel)] bg-white pb-[env(safe-area-inset-bottom)] shadow-[var(--shadow-floating)] outline-none xl:hidden"
        :class="{ 'app-bottom-sheet--dragging': dragging }"
        :style="sheetStyle"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        :data-snap="snap"
        tabindex="-1"
        @keydown="handleKeydown"
      >
        <header class="relative z-10 shrink-0 border-b border-slate-200 bg-white">
          <div
            class="flex h-11 touch-none items-center justify-center"
            data-sheet-drag-handle
            aria-hidden="true"
            @pointerdown="startHandleDrag"
            @pointermove="continueDrag"
            @pointerup="finishDrag"
            @pointercancel="cancelDrag"
          >
            <span class="h-1 w-10 rounded-full bg-[var(--c-border-strong)]" />
          </div>
          <div class="flex min-h-14 items-center justify-between gap-3 px-4 pb-3">
            <h2 :id="titleId" class="min-w-0 text-base font-bold text-slate-950">{{ title }}</h2>
            <button class="grid size-11 shrink-0 place-items-center rounded-xl hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" :aria-label="closeLabel || `${title} schließen`" @click="requestClose">
              <X class="size-5" aria-hidden="true" />
            </button>
          </div>
        </header>

        <div
          ref="scroller"
          class="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain bg-[var(--c-surface)] p-3"
          data-sheet-scroll
          @pointerdown="prepareContentDrag"
          @pointermove="continueDrag"
          @pointerup="finishDrag"
          @pointercancel="cancelDrag"
          @touchstart="prepareContentTouch"
          @touchmove="continueContentTouch"
          @touchend="finishContentTouch"
          @touchcancel="cancelDrag"
        >
          <slot />
        </div>

        <footer v-if="$slots.footer" class="shrink-0 border-t border-slate-200 bg-white px-4 py-3">
          <slot name="footer" />
        </footer>
      </section>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { resetBottomSheetScroll, shouldResetBottomSheetScroll, type BottomSheetContentKey } from '~/utils/bottomSheetScroll'

type SheetSnap = 'medium' | 'expanded'
type DragSource = 'handle' | 'content'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  initialSnap?: SheetSnap
  closeOnOverlay?: boolean
  closeLabel?: string
  contentKey?: BottomSheetContentKey
}>(), {
  initialSnap: 'medium',
  closeOnOverlay: true,
  contentKey: null
})

const emit = defineEmits<{
  'update:open': [open: boolean]
  close: []
  snapChange: [snap: SheetSnap]
}>()

const panel = ref<HTMLElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const titleId = `bottom-sheet-title-${useId()}`
const snap = ref<SheetSnap>(props.initialSnap)
const panelHeight = ref(0)
const dragging = ref(false)
let returnFocusTo: HTMLElement | null = null
let dragPointerId: number | null = null
let dragStartY = 0
let dragStartHeight = 0
let dragStartedAt = 0
let dragSource: DragSource | null = null
let contentDragPending = false
let contentTouchActive = false
let contentTouchLastY = 0

const viewportHeight = () => Math.max(1, Math.round(window.visualViewport?.height || window.innerHeight))
const snapHeight = (value: SheetSnap) => {
  const height = viewportHeight()
  return value === 'expanded' ? Math.min(height - 8, height * 0.94) : Math.min(height - 8, height * 0.6)
}
const sheetStyle = computed(() => ({
  height: `${panelHeight.value}px`,
  maxHeight: 'calc(100dvh - 0.5rem)'
}))

watch([() => props.open, () => props.contentKey], async ([open, contentKey], [wasOpen, previousContentKey]) => {
  if (!import.meta.client) return
  if (!open) {
    if (wasOpen) cleanupOpenState()
    return
  }

  if (!wasOpen) {
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null
    snap.value = props.initialSnap
    panelHeight.value = snapHeight(snap.value)
    document.body.classList.add('drawer-open')
    window.addEventListener('resize', handleViewportChange)
    window.addEventListener('orientationchange', handleOrientationChange)
    window.visualViewport?.addEventListener('resize', handleViewportChange)
  }

  if (shouldResetBottomSheetScroll(open, wasOpen, contentKey, previousContentKey)) await resetScrollPosition()
  if (!wasOpen) panel.value?.focus()
}, { immediate: true })

onBeforeUnmount(cleanupOpenState)

function requestClose() {
  emit('update:open', false)
  emit('close')
}

function setSnap(value: SheetSnap) {
  snap.value = value
  panelHeight.value = snapHeight(value)
  emit('snapChange', value)
}

function startHandleDrag(event: PointerEvent) {
  if (!event.isPrimary) return
  beginDrag(event, 'handle', true)
}

function prepareContentDrag(event: PointerEvent) {
  if (!event.isPrimary || event.pointerType === 'touch' || scroller.value?.scrollTop !== 0 || isInteractiveTarget(event.target)) return
  beginDrag(event, 'content', false)
}

function beginDrag(event: PointerEvent, source: DragSource, immediate: boolean) {
  dragPointerId = event.pointerId
  dragStartY = event.clientY
  dragStartHeight = panelHeight.value
  dragStartedAt = performance.now()
  dragSource = source
  contentDragPending = !immediate
  dragging.value = immediate
  if (immediate) (event.currentTarget as HTMLElement)?.setPointerCapture(event.pointerId)
}

function continueDrag(event: PointerEvent) {
  if (event.pointerId !== dragPointerId || !dragSource) return
  const deltaY = event.clientY - dragStartY
  if (contentDragPending) {
    if (deltaY <= 8 || scroller.value?.scrollTop !== 0) return
    contentDragPending = false
    dragging.value = true
    ;(event.currentTarget as HTMLElement)?.setPointerCapture(event.pointerId)
  }
  if (!dragging.value) return
  event.preventDefault()
  const maximum = snapHeight('expanded')
  panelHeight.value = Math.max(96, Math.min(maximum, dragStartHeight - deltaY))
}

function finishDrag(event: PointerEvent) {
  if (event.pointerId !== dragPointerId || !dragSource) return
  if (!dragging.value) {
    resetDrag()
    return
  }
  finishGesture(event.clientY - dragStartY)
}

function finishGesture(deltaY: number) {
  const elapsed = Math.max(1, performance.now() - dragStartedAt)
  const velocity = deltaY / elapsed
  const closeThreshold = Math.max(90, viewportHeight() * 0.12)
  if (deltaY > closeThreshold || velocity > 0.75 || panelHeight.value < snapHeight('medium') * 0.7) {
    resetDrag()
    requestClose()
    return
  }
  const midpoint = (snapHeight('medium') + snapHeight('expanded')) / 2
  setSnap(deltaY < -48 || panelHeight.value > midpoint ? 'expanded' : 'medium')
  resetDrag()
}

function prepareContentTouch(event: TouchEvent) {
  const touch = event.touches[0]
  if (!touch || scroller.value?.scrollTop !== 0 || isInteractiveTarget(event.target)) return
  dragStartY = touch.clientY
  contentTouchLastY = touch.clientY
  dragStartHeight = panelHeight.value
  dragStartedAt = performance.now()
  dragSource = 'content'
  contentTouchActive = true
  contentDragPending = true
}

function continueContentTouch(event: TouchEvent) {
  if (!contentTouchActive || !dragSource) return
  const touch = event.touches[0]
  if (!touch) return
  contentTouchLastY = touch.clientY
  const deltaY = touch.clientY - dragStartY
  if (contentDragPending) {
    if (deltaY <= 8 || scroller.value?.scrollTop !== 0) return
    contentDragPending = false
    dragging.value = true
  }
  if (!dragging.value) return
  event.preventDefault()
  panelHeight.value = Math.max(96, Math.min(snapHeight('expanded'), dragStartHeight - deltaY))
}

function finishContentTouch() {
  if (!contentTouchActive) return
  const deltaY = contentTouchLastY - dragStartY
  contentTouchActive = false
  if (!dragging.value) {
    resetDrag()
    return
  }
  finishGesture(deltaY)
}

function cancelDrag() {
  if (dragging.value) setSnap(snap.value)
  resetDrag()
}

function resetDrag() {
  dragging.value = false
  contentDragPending = false
  contentTouchActive = false
  dragPointerId = null
  dragSource = null
}

async function resetScrollPosition() {
  await resetBottomSheetScroll(() => scroller.value)
}

function handleViewportChange() {
  // Mobile browser chrome can resize the visual viewport while the sheet body
  // scrolls. Keep the panel (and therefore its fixed header) stable until the
  // user returns to the top; CSS max-height still guards the visible viewport.
  if (!dragging.value && (scroller.value?.scrollTop || 0) === 0) {
    panelHeight.value = snapHeight(snap.value)
  }
}

function handleOrientationChange() {
  window.setTimeout(handleViewportChange, 180)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
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
  } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.value)) {
    event.preventDefault()
    first?.focus()
  }
}

function cleanupOpenState() {
  if (!import.meta.client) return
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('orientationchange', handleOrientationChange)
  window.visualViewport?.removeEventListener('resize', handleViewportChange)
  document.body.classList.remove('drawer-open')
  resetDrag()
  returnFocusTo?.focus()
  returnFocusTo = null
}

function isInteractiveTarget(target: EventTarget | null) {
  return target instanceof Element && !!target.closest('button, a, input, select, textarea, label, [role], svg, [data-sheet-no-drag]')
}
</script>

<style scoped>
.app-bottom-sheet {
  transition: height 250ms ease-out, transform 250ms ease-out;
}

.app-bottom-sheet--dragging {
  transition: none;
  user-select: none;
}

.app-sheet-backdrop-enter-active,
.app-sheet-backdrop-leave-active {
  transition: opacity 250ms ease-out;
}

.app-sheet-backdrop-enter-from,
.app-sheet-backdrop-leave-to {
  opacity: 0;
}

.app-sheet-panel-enter-active,
.app-sheet-panel-leave-active {
  transition: transform 250ms ease-out;
}

.app-sheet-panel-enter-from,
.app-sheet-panel-leave-to {
  transform: translateY(100%);
}

@media (prefers-reduced-motion: reduce) {
  .app-bottom-sheet,
  .app-sheet-backdrop-enter-active,
  .app-sheet-backdrop-leave-active,
  .app-sheet-panel-enter-active,
  .app-sheet-panel-leave-active {
    transition-duration: 1ms;
  }
}
</style>
