<template>
  <Card class="p-5 sm:p-7">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div><p class="civic-kicker">Benachrichtigungen</p><h2 class="mt-1 text-lg font-black text-slate-950">Relevante Benachrichtigungen</h2><p class="mt-2 max-w-2xl text-sm leading-6 text-slate-600">In-App-Hinweise informieren nur über fachliche Änderungen. Kartenbewegungen, Filter und andere technische Interaktionen erzeugen keine Meldungen.</p></div>
      <p class="text-xs font-bold" :class="state === 'error' ? 'text-rose-700' : 'text-slate-500'" role="status" aria-live="polite">{{ statusLabel }}</p>
    </div>
    <div v-if="store.preferencesLoading || !store.preferences" class="mt-5 h-48 animate-pulse rounded-xl bg-slate-100" />
    <fieldset v-else class="mt-5 divide-y divide-slate-200" :disabled="state === 'saving'">
      <legend class="sr-only">In-App-Benachrichtigungen auswählen</legend>
      <label v-for="option in options" :key="option.key" class="flex min-h-16 cursor-pointer items-center justify-between gap-4 py-3">
        <span><span class="block text-sm font-bold text-slate-900">{{ option.label }}</span><span class="mt-0.5 block text-xs leading-5 text-slate-500">{{ option.description }}</span></span>
        <input class="size-5 shrink-0 accent-[#0b8190]" type="checkbox" :checked="store.preferences[option.key]" @change="toggle(option.key, $event)">
      </label>
    </fieldset>
    <button v-if="state === 'error'" class="mt-3 min-h-10 cursor-pointer rounded-lg px-3 text-sm font-bold text-[#154d73] hover:bg-slate-100" type="button" @click="queue.retry()">Erneut versuchen</button>
    <p class="mt-4 text-xs leading-5 text-slate-500">Konto- und Sicherheitsmeldungen bleiben unabhängig von diesen Einstellungen aktiv. E-Mail und Web-Push sind derzeit nicht aktiviert.</p>
  </Card>
</template>

<script setup lang="ts">
import type { NotificationPreferences } from '~/types/notification'
import { createSerialSaveQueue, type SerialSaveState } from '~/utils/serialSaveQueue'

type PreferenceKey = 'in_app_enabled' | 'notify_gis' | 'notify_osm' | 'notify_area_updates' | 'notify_social' | 'notify_system'
type PreferenceFields = Pick<NotificationPreferences, PreferenceKey>
const store = useNotificationsStore()
const state = ref<SerialSaveState>('saved')
const options: Array<{ key: PreferenceKey, label: string, description: string }> = [
  { key: 'in_app_enabled', label: 'In-App-Benachrichtigungen', description: 'Persönliches Notification Center und relevante Realtime-Hinweise.' },
  { key: 'notify_gis', label: 'GIS-Aktivitäten', description: 'Wesentliche Änderungen an eigenen oder beobachteten Flächen.' },
  { key: 'notify_osm', label: 'OpenStreetMap', description: 'Übernahmen und wesentliche Änderungen verknüpfter OSM-Quellen.' },
  { key: 'notify_area_updates', label: 'Gebiets- und Datenupdates', description: 'Neue Statistiken für beobachtete Gebiete.' },
  { key: 'notify_social', label: 'Social Publishing', description: 'Freigaben, Veröffentlichungen und Fehler für Berechtigte.' },
  { key: 'notify_system', label: 'System und Importe', description: 'Relevante Import- und Synchronisationszustände.' }
]
const queue = createSerialSaveQueue<PreferenceFields, NotificationPreferences>({
  save: patch => store.savePreferences(patch),
  onStateChange: value => { state.value = value }
})
const statusLabel = computed(() => state.value === 'saving' ? 'Wird gespeichert …' : state.value === 'error' ? 'Speichern fehlgeschlagen' : 'Gespeichert')

function toggle(key: PreferenceKey, event: Event) {
  if (!store.preferences) return
  const value = (event.target as HTMLInputElement).checked
  store.preferences[key] = value
  queue.enqueue({ [key]: value })
}

onMounted(() => { if (!store.preferences) void store.loadPreferences() })
</script>
