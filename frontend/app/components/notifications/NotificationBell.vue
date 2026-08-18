<template>
  <div ref="root" class="relative shrink-0">
    <button
      class="relative grid size-11 cursor-pointer place-items-center rounded-xl text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
      type="button"
      aria-label="Benachrichtigungen"
      :aria-expanded="open"
      aria-haspopup="dialog"
      @click="toggle"
    >
      <Bell class="size-5" aria-hidden="true" />
      <span v-if="store.unreadCount" class="absolute right-0.5 top-0.5 grid min-w-4 place-items-center rounded-full bg-rose-600 px-1 text-[9px] font-black leading-4 text-white" aria-hidden="true">{{ badge }}</span>
      <span class="sr-only">{{ store.unreadCount }} ungelesene Benachrichtigungen</span>
    </button>

    <div v-if="mode === 'desktop' && open" class="absolute right-0 top-[calc(100%+0.5rem)] z-[100] w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_18px_46px_rgba(15,23,42,0.18)]" role="dialog" aria-label="Benachrichtigungen">
      <div class="mb-2 flex items-center justify-between gap-3 px-1"><h2 class="text-base font-black text-slate-950">Benachrichtigungen</h2><button class="grid size-9 cursor-pointer place-items-center rounded-lg hover:bg-slate-100" type="button" aria-label="Benachrichtigungen schließen" @click="open = false"><X class="size-4" /></button></div>
      <div class="max-h-[min(70dvh,36rem)] overflow-y-auto overscroll-contain"><NotificationCenterContent @close="open = false" /></div>
    </div>

    <AppBottomSheet v-if="mode === 'mobile'" :open="open" title="Benachrichtigungen" close-label="Benachrichtigungen schließen" content-key="notifications" initial-snap="expanded" @update:open="open = $event">
      <NotificationCenterContent @close="open = false" />
    </AppBottomSheet>
  </div>
</template>

<script setup lang="ts">
import { Bell, X } from 'lucide-vue-next'

const props = defineProps<{ mode: 'desktop' | 'mobile' }>()
const store = useNotificationsStore()
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const badge = computed(() => store.unreadCount > 99 ? '99+' : String(store.unreadCount))

function toggle() {
  open.value = !open.value
  if (open.value) void store.fetchNotifications()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}

function onPointerdown(event: PointerEvent) {
  if (props.mode === 'desktop' && open.value && root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('pointerdown', onPointerdown)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('pointerdown', onPointerdown)
})
</script>
