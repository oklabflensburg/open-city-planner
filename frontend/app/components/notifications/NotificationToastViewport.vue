<template>
  <div class="pointer-events-none fixed inset-x-3 top-20 z-[120] ml-auto flex max-w-sm flex-col gap-2 sm:left-auto sm:right-4" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="notification-toast">
      <div v-for="toast in store.toasts" :key="toast.id" class="pointer-events-auto flex items-start gap-3 rounded-2xl border bg-white p-4 shadow-xl" :class="toastStyle(toast.priority)" role="status">
        <component :is="toastIcon(toast.priority)" class="mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <div class="min-w-0 flex-1"><p class="text-sm font-black">{{ toast.title }}</p><p v-if="toast.message" class="mt-1 text-xs leading-5 text-slate-600">{{ toast.message }}</p></div>
        <button class="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg hover:bg-slate-100" type="button" aria-label="Benachrichtigung schließen" @click="store.dismissToast(toast.id)"><X class="size-4" /></button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Info, X } from '@lucide/vue'
import type { NotificationPriority } from '~/types/notification'

const store = useNotificationsStore()
const toastIcon = (priority: NotificationPriority) => priority === 'SUCCESS' ? CheckCircle2 : priority === 'INFO' ? Info : AlertTriangle
const toastStyle = (priority: NotificationPriority) => priority === 'SUCCESS' ? 'border-emerald-200 text-emerald-900' : priority === 'ERROR' ? 'border-rose-200 text-rose-900' : priority === 'WARNING' ? 'border-amber-200 text-amber-900' : 'border-cyan-200 text-slate-900'
</script>

<style scoped>
.notification-toast-enter-active, .notification-toast-leave-active { transition: opacity 160ms ease, transform 160ms ease; }
.notification-toast-enter-from, .notification-toast-leave-to { opacity: 0; transform: translateY(-0.5rem); }
</style>
