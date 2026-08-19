<template>
  <Card id="benachrichtigungen" class="p-5 sm:p-7">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div><p class="civic-kicker">Benachrichtigungen</p><h2 class="mt-1 text-lg font-black text-slate-950">Zustellwege festlegen</h2><p class="mt-2 max-w-2xl text-sm leading-6 text-slate-600">In-App-Hinweise und optionale E-Mails können unabhängig voneinander gesteuert werden.</p></div>
      <p class="text-xs font-bold" :class="state === 'error' ? 'text-rose-700' : 'text-slate-500'" role="status" aria-live="polite">{{ statusLabel }}</p>
    </div>
    <div v-if="store.preferencesLoading || !store.preferences" class="mt-5 h-64 animate-pulse rounded-xl bg-slate-100" />
    <div v-else class="mt-5" :aria-busy="state === 'saving'">
      <div class="grid grid-cols-[1fr_5.5rem_5.5rem] items-center gap-2 border-b border-slate-200 pb-3 text-center text-xs font-bold uppercase tracking-wide text-slate-500">
        <span class="text-left">Kategorie</span><span>Im Stadtplaner</span><span>E-Mail</span>
      </div>
      <div class="grid grid-cols-[1fr_5.5rem_5.5rem] items-center gap-2 border-b border-slate-100 py-3">
        <span class="text-sm font-bold text-slate-900">Alle optionalen Benachrichtigungen</span>
        <input class="mx-auto size-5 accent-[#0b8190]" type="checkbox" aria-label="In-App-Benachrichtigungen aktivieren" :checked="store.preferences.in_app_enabled" @change="toggle('in_app_enabled', $event)">
        <input class="mx-auto size-5 accent-[#0b8190]" type="checkbox" aria-label="E-Mail-Benachrichtigungen aktivieren" :checked="store.preferences.email_enabled" @change="toggle('email_enabled', $event)">
      </div>
      <div v-for="row in rows" :key="row.label" class="grid grid-cols-[1fr_5.5rem_5.5rem] items-center gap-2 border-b border-slate-100 py-3">
        <span><span class="block text-sm font-semibold text-slate-900">{{ row.label }}</span><span class="text-xs text-slate-500">{{ row.description }}</span></span>
        <input class="mx-auto size-5 accent-[#0b8190]" type="checkbox" :aria-label="`${row.label} im Stadtplaner`" :checked="store.preferences[row.inApp]" @change="toggle(row.inApp, $event)">
        <input class="mx-auto size-5 accent-[#0b8190]" type="checkbox" :aria-label="`${row.label} per E-Mail`" :checked="store.preferences[row.email]" @change="toggle(row.email, $event)">
      </div>
      <label class="mt-6 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4">
        <input class="mt-0.5 size-5 accent-[#0b8190]" type="checkbox" :checked="store.preferences.newsletter_enabled" @change="toggle('newsletter_enabled', $event)">
        <span><strong class="block text-sm text-slate-950">Newsletter</strong><span class="mt-1 block text-xs leading-5 text-slate-600">Neuigkeiten rund um den Stadtplaner und das OK Lab Flensburg per E-Mail erhalten.</span></span>
      </label>
    </div>
    <button v-if="state === 'error'" class="mt-3 min-h-10 cursor-pointer rounded-lg px-3 text-sm font-bold text-[#154d73] hover:bg-slate-100" type="button" @click="queue.retry()">Erneut versuchen</button>
    <p class="mt-4 text-xs leading-5 text-slate-500">Konto- und Sicherheitsmeldungen sowie notwendige Serviceinformationen werden unabhängig von diesen Einstellungen zugestellt.</p>
  </Card>
</template>

<script setup lang="ts">
import type { NotificationPreferences } from '~/types/notification'
import { createSerialSaveQueue, type SerialSaveState } from '~/utils/serialSaveQueue'

type PreferenceKey = Exclude<keyof NotificationPreferences, 'updated_at' | 'notify_account'>
type PreferenceFields = Partial<Pick<NotificationPreferences, PreferenceKey>>
const store = useNotificationsStore()
const state = ref<SerialSaveState>('saved')
const rows: Array<{ label: string, description: string, inApp: PreferenceKey, email: PreferenceKey }> = [
  { label: 'GIS', description: 'Eigene und beobachtete Flächen', inApp: 'notify_gis', email: 'email_notify_gis' },
  { label: 'OpenStreetMap', description: 'Wesentliche Änderungen an OSM-Quellen', inApp: 'notify_osm', email: 'email_notify_osm' },
  { label: 'Gebiete und Daten', description: 'Neue Statistik- und Gebietsdaten', inApp: 'notify_area_updates', email: 'email_notify_area_updates' },
  { label: 'Social', description: 'Freigaben und Versandfehler', inApp: 'notify_social', email: 'email_notify_social' },
  { label: 'System', description: 'Geeignete System- und Importmeldungen', inApp: 'notify_system', email: 'email_notify_system' }
]
const queue = createSerialSaveQueue<PreferenceFields, NotificationPreferences>({
  save: patch => store.savePreferences(patch),
  onStateChange: value => { state.value = value }
})
const statusLabel = computed(() => state.value === 'saving' ? 'Wird gespeichert …' : state.value === 'error' ? 'Speichern fehlgeschlagen' : 'Gespeichert')

function toggle(key: PreferenceKey, event: Event) {
  if (!store.preferences) return
  const value = (event.target as HTMLInputElement).checked
  store.preferences[key] = value as never
  queue.enqueue({ [key]: value } as PreferenceFields)
}

onMounted(() => { if (!store.preferences) void store.loadPreferences() })
</script>
