<template>
  <div class="min-w-0" data-notification-center>
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
      <div class="flex gap-1 overflow-x-auto" role="tablist" aria-label="Benachrichtigungen filtern">
        <button
          v-for="option in filters"
          :key="option.value"
          class="min-h-9 shrink-0 rounded-lg px-3 text-xs font-bold"
          :class="filter === option.value ? 'bg-[#e2edf4] text-[#154d73]' : 'text-slate-600 hover:bg-slate-100'"
          type="button"
          role="tab"
          :aria-selected="filter === option.value"
          @click="selectFilter(option.value)"
        >{{ option.label }}</button>
      </div>
      <button v-if="store.unreadCount" class="min-h-9 rounded-lg px-2 text-xs font-bold text-[#154d73] hover:bg-slate-100" type="button" @click="store.markAllRead()">Alle gelesen</button>
    </div>

    <div v-if="store.loading && !store.items.length" class="grid min-h-56 place-items-center text-sm text-slate-500" role="status">Benachrichtigungen werden geladen …</div>
    <div v-else-if="!store.items.length" class="grid min-h-56 place-items-center px-6 text-center">
      <div><BellOff class="mx-auto size-8 text-slate-400" aria-hidden="true" /><p class="mt-3 font-bold text-slate-800">Keine Benachrichtigungen</p><p class="mt-1 text-sm text-slate-500">Relevante Änderungen erscheinen hier.</p></div>
    </div>
    <ul v-else class="divide-y divide-slate-200" aria-label="Benachrichtigungsliste">
      <li v-for="item in store.items" :key="item.id">
        <button
          class="grid min-h-20 w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-2 py-3 text-left hover:bg-slate-50"
          :class="item.is_read ? 'bg-white' : 'bg-[#edf7f8]'"
          type="button"
          @click="openNotification(item)"
        >
          <span class="mt-0.5 grid size-9 place-items-center rounded-xl" :class="categoryStyle(item.category)"><component :is="categoryIcon(item.category)" class="size-4" aria-hidden="true" /></span>
          <span class="min-w-0"><span class="flex items-center gap-2 text-sm font-bold text-slate-900"><span v-if="!item.is_read" class="size-2 shrink-0 rounded-full bg-[#0b8190]" aria-hidden="true" /><span class="truncate">{{ item.title }}</span><span v-if="!item.is_read" class="sr-only">Ungelesen</span></span><span class="mt-1 block text-xs leading-5 text-slate-600">{{ item.message }}</span><span v-if="item.action_label" class="mt-1 block text-xs font-bold text-[#154d73]">{{ item.action_label }} →</span></span>
          <time class="whitespace-nowrap pt-0.5 text-[10px] text-slate-500" :datetime="item.created_at">{{ formatNotificationTime(item.created_at) }}</time>
        </button>
      </li>
    </ul>
    <button v-if="store.page < store.pages" class="mt-3 min-h-11 w-full rounded-xl border border-slate-300 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="loadMore">Mehr laden</button>
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle, BellOff, Database, MapPin, Settings, Share2, ShieldCheck } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { AppNotification, NotificationCategory } from '~/types/notification'
import { formatNotificationTime, safeNotificationTarget } from '~/utils/notifications'

const emit = defineEmits<{ close: [] }>()
const store = useNotificationsStore()
const filter = ref<'ALL' | 'UNREAD' | NotificationCategory>('ALL')
const filters = [
  { value: 'ALL' as const, label: 'Alle' },
  { value: 'UNREAD' as const, label: 'Ungelesen' },
  { value: 'GIS' as const, label: 'GIS' },
  { value: 'DATA' as const, label: 'Daten' },
  { value: 'SYSTEM' as const, label: 'System' }
]

async function selectFilter(value: typeof filter.value) {
  filter.value = value
  await store.fetchNotifications({
    category: value === 'ALL' || value === 'UNREAD' ? undefined : value,
    unreadOnly: value === 'UNREAD'
  })
}

async function loadMore() {
  await store.fetchNotifications({
    page: store.page + 1,
    category: filter.value === 'ALL' || filter.value === 'UNREAD' ? undefined : filter.value,
    unreadOnly: filter.value === 'UNREAD',
    append: true
  })
}

async function openNotification(item: AppNotification) {
  await store.markRead(item.id)
  emit('close')
  const target = safeNotificationTarget(item.action_url)
  if (target) await navigateTo(target)
}

const icons: Record<NotificationCategory, Component> = {
  GIS: MapPin, DATA: Database, OSM: MapPin, SOCIAL: Share2,
  ACCOUNT: ShieldCheck, ADMIN: Settings, SYSTEM: AlertTriangle
}
const categoryIcon = (category: NotificationCategory) => icons[category]
const categoryStyle = (category: NotificationCategory) => ({
  GIS: 'bg-teal-50 text-teal-700', DATA: 'bg-blue-50 text-blue-700', OSM: 'bg-cyan-50 text-cyan-700',
  SOCIAL: 'bg-violet-50 text-violet-700', ACCOUNT: 'bg-amber-50 text-amber-700',
  ADMIN: 'bg-slate-100 text-slate-700', SYSTEM: 'bg-rose-50 text-rose-700'
})[category]
</script>
