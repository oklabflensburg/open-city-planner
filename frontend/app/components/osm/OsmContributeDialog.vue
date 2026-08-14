<template>
  <AppModal
    :open="open"
    title="OpenStreetMap verbessern"
    description="Die angezeigten Referenzdaten können direkt bei OpenStreetMap ergänzt oder korrigiert werden."
    size="md"
    @update:open="$emit('update:open', $event)"
  >
    <div class="space-y-4 text-sm leading-6 text-slate-700">
      <p>Stadtplaner verändert OpenStreetMap nicht. Wählen Sie das passende externe Werkzeug für Ihren Beitrag.</p>
      <div class="grid gap-3">
        <a
          v-for="action in actions"
          :key="action.key"
          class="group rounded-xl border border-slate-200 p-4 transition hover:border-[#154d73] hover:bg-slate-50"
          :href="action.href"
          target="_blank"
          rel="noopener noreferrer"
          :aria-label="`${action.title} – öffnet neuen Tab`"
        >
          <span class="flex min-h-11 items-center justify-between gap-3 font-bold text-[#154d73]">
            {{ action.title }} <ExternalLink class="size-4 shrink-0" aria-hidden="true" />
          </span>
          <span class="mt-1 block text-xs leading-5 text-slate-600">{{ action.description }}</span>
        </a>
      </div>
      <p class="text-xs text-slate-500">Die externen Seiten werden erst nach Ihrem Klick aufgerufen. Eine gegebenenfalls erforderliche Anmeldung erfolgt bei OpenStreetMap.</p>
    </div>
    <template #footer>
      <button class="page-button-secondary w-full sm:w-auto" type="button" @click="$emit('update:open', false)">Abbrechen</button>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'
import { getOsmIdEditorUrl, getStreetCompleteUrl } from '~/utils/osmLinks'

const props = defineProps<{
  open: boolean
  latitude?: number
  longitude?: number
  zoom?: number
}>()
defineEmits<{ 'update:open': [open: boolean] }>()

const isAndroid = computed(() => import.meta.client && /Android/i.test(navigator.userAgent))
const streetComplete = computed(() => ({
  key: 'streetcomplete',
  title: isAndroid.value ? 'Mit StreetComplete ergänzen' : 'StreetComplete kennenlernen',
  description: 'Ein aufgabenorientierter OpenStreetMap-Editor für einfache Ergänzungen vor Ort auf Android.',
  href: getStreetCompleteUrl()
}))
const idEditor = computed(() => ({
  key: 'id',
  title: 'Mit iD bearbeiten',
  description: 'Der browserbasierte OpenStreetMap-Editor für umfangreichere Änderungen an Punkten und Flächen.',
  href: getOsmIdEditorUrl({ latitude: props.latitude, longitude: props.longitude, zoom: props.zoom })
}))
const actions = computed(() => isAndroid.value
  ? [streetComplete.value, idEditor.value]
  : [idEditor.value, streetComplete.value])
</script>
