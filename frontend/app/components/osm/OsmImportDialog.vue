<template>
  <AppModal
    :open="open"
    title="OpenStreetMap-Objekt übernehmen?"
    description="Die OSM-Geometrie und öffentliche Angaben dienen als Ausgangspunkt für eine eigene Stadtplaner-Fläche. OpenStreetMap selbst bleibt unverändert."
    :busy="importing"
    @update:open="$emit('update:open', $event)"
  >
    <div class="space-y-4 text-sm">
      <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <p class="font-bold text-slate-950">{{ displayName || 'OSM-Objekt' }}</p>
        <p class="mt-1 text-slate-600">{{ categoryLabel }}</p>
        <p v-if="address" class="mt-1 text-slate-600">{{ address }}</p>
        <span v-if="detail?.occupancy_status === 'VACANT'" class="mt-3 inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">Leerstand laut OpenStreetMap</span>
      </div>
      <label class="block">
        <span class="field-label">Etage</span>
        <select v-model="floor" class="field-input">
          <option :value="null">Aus OSM übernehmen / nicht angegeben</option>
          <option v-for="item in floors" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <p v-if="feature.properties.feature_type === 'point'" class="rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-900">Für diesen Punkt sucht Stadtplaner serverseitig eine passende umschließende OSM-Fläche. Wird keine gefunden, wechseln Sie anschließend zum manuellen Zeichnen.</p>
      <p v-if="error" class="rounded-xl bg-rose-50 px-4 py-3 font-semibold text-rose-800" role="alert">{{ error }}</p>
    </div>
    <template #footer>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button class="page-button-secondary w-full sm:w-auto" type="button" :disabled="importing" @click="$emit('update:open', false)">Abbrechen</button>
        <button class="page-button-primary w-full sm:w-auto" type="button" :disabled="importing" @click="confirmImport">
          <LoaderCircle v-if="importing" class="size-4 animate-spin" aria-hidden="true" />
          {{ importing ? 'Wird übernommen …' : 'Fläche übernehmen' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'
import { ApiError } from '~/composables/useApi'
import type { OsmFeatureDetail, OsmViewportFeature } from '~/types/osm'
import { osmObjectTags } from '~/utils/osm'
import { osmCategoryLabels } from '~/utils/osmCategories'
import { formatOsmCategory, localizedOsmName } from '~/utils/osmTranslations'

const props = defineProps<{ open: boolean, feature: OsmViewportFeature, detail: OsmFeatureDetail | null }>()
const emit = defineEmits<{ 'update:open': [open: boolean] }>()
const { importing, error, importFeature } = useOsmImport()
const floor = ref<string | null>(null)
const floors = ['UG', 'EG', '1OG', '2OG', '3OG', 'DG']
const tags = computed(() => props.detail ? osmObjectTags(props.detail) : {})
const displayName = computed(() => localizedOsmName(tags.value, props.detail?.name || props.feature.properties.name))
const categoryLabel = computed(() => props.detail
  ? formatOsmCategory(tags.value).value
  : osmCategoryLabels[props.feature.properties.category])
const address = computed(() => {
  const value = props.detail?.address
  return value ? [[value.street, value.house_number].filter(Boolean).join(' '), [value.postal_code, value.city].filter(Boolean).join(' ')].filter(Boolean).join(', ') : ''
})

async function confirmImport() {
  if (importing.value) return
  try {
    const created = await importFeature({
      osm_type: props.feature.properties.osm_type,
      osm_id: props.feature.properties.osm_id,
      floor: floor.value
    })
    emit('update:open', false)
    await navigateTo(`/flaechen/${created.slug}`)
  } catch (cause) {
    if (!(cause instanceof ApiError)) return
    if (cause.code === 'OSM_GEOMETRY_REQUIRED') {
      emit('update:open', false)
      await navigateTo({ path: '/flaechen/neu', query: {
        osm_type: props.feature.properties.osm_type,
        osm_id: String(props.feature.properties.osm_id),
        floor: floor.value || undefined
      } })
      return
    }
    if (cause.code === 'OSM_FEATURE_ALREADY_IMPORTED') {
      const details = cause.details as { error?: { slug?: string } } | undefined
      if (details?.error?.slug) await navigateTo(`/flaechen/${details.error.slug}`)
    }
  }
}
</script>
