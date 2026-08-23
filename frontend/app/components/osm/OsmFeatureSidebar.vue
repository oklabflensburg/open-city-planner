<template>
  <section v-if="feature" :class="embedded ? 'min-w-0 bg-white p-1' : 'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm'" aria-live="polite">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-[10px] font-bold uppercase tracking-wide text-[#154d73]">OpenStreetMap · {{ categoryLabel }}</p>
        <h2 class="mt-1 break-words text-base font-bold text-slate-950">{{ displayName || typeLabel }}</h2>
        <p class="mt-1 text-xs text-slate-500">{{ typeLabel }}</p>
      </div>
      <button v-if="!embedded" class="grid size-11 shrink-0 cursor-pointer place-items-center rounded-xl text-slate-500 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" aria-label="OSM-Auswahl schließen" @click="closeSelection">
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>

    <div v-if="isVacant" class="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-950">
      <span class="font-bold">Status: Leerstand</span>
      <span class="mt-0.5 block text-amber-800">Datenquelle: OpenStreetMap</span>
    </div>

    <dl v-if="feature.properties.canonical_category || feature.properties.canonical_floor || feature.properties.mapped_area_m2" class="mt-3 grid gap-2 rounded-xl bg-slate-50 p-3 text-xs">
      <div v-if="feature.properties.canonical_category" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Branche</dt><dd>{{ getIndustryLabel(feature.properties.canonical_category) }}</dd></div>
      <div v-if="feature.properties.canonical_floor" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Etage</dt><dd>{{ feature.properties.canonical_floor }}</dd></div>
      <div v-if="feature.properties.mapped_area_m2" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Kartierte Fläche</dt><dd>{{ Math.round(feature.properties.mapped_area_m2).toLocaleString('de-DE') }} m²</dd></div>
    </dl>

    <div v-if="osm.detailLoading" class="mt-3 flex items-center gap-2 text-xs text-slate-500">
      <LoaderCircle class="size-4 animate-spin" aria-hidden="true" /> Details werden geladen …
    </div>
    <p v-else-if="osm.detailError" class="mt-3 text-xs text-rose-700" role="alert">{{ osm.detailError }}</p>
    <dl v-else-if="detail" class="mt-3 grid gap-2 text-xs">
      <div class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">{{ detailCategory.label }}</dt><dd class="break-words">{{ detailCategory.value }}</dd></div>
      <div v-for="item in localizedDetails" :key="item.label" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">{{ item.label }}</dt><dd class="break-words">{{ item.value }}</dd></div>
      <div v-if="address" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Adresse</dt><dd class="break-words">{{ address }}</dd></div>
      <div v-if="detail.opening_hours" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Öffnung</dt><dd class="break-words">{{ detail.opening_hours }}</dd></div>
      <div v-if="detail.brand" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Marke</dt><dd class="break-words">{{ detail.brand }}</dd></div>
      <div v-if="detail.operator" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Betreiber</dt><dd class="break-words">{{ detail.operator }}</dd></div>
      <div v-if="detail.building_levels" class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2"><dt class="text-slate-500">Geschosse</dt><dd>{{ detail.building_levels }}</dd></div>
    </dl>

    <AreaExternalLinks
      v-if="detail && (detail.external_links.wikipedia || detail.external_links.wikidata)"
      class="mt-4"
      :area-name="displayName || typeLabel"
      :links="detail.external_links"
    />

    <div class="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs font-bold">
      <a v-if="safeWebsite" class="inline-flex min-h-11 items-center text-[#154d73] underline" :href="safeWebsite" target="_blank" rel="noopener noreferrer">Website</a>
      <a class="inline-flex min-h-11 items-center gap-1.5 text-[#154d73] underline" :href="osmUrl" target="_blank" rel="noopener noreferrer" aria-label="OpenStreetMap-Objekt öffnen"><ProviderIcon provider="openstreetmap" class="size-4" /> Auf OpenStreetMap ansehen</a>
    </div>

    <div v-if="feature.properties.stadtplaner?.length" class="mt-3 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-950">
      <p class="font-bold">Bereits im Stadtplaner</p>
      <p v-if="feature.properties.stadtplaner.length > 1" class="mt-1">{{ feature.properties.stadtplaner.length }} verknüpfte Flächen</p>
      <NuxtLink v-for="polygon in feature.properties.stadtplaner" :key="polygon.id" class="mt-1 block min-h-11 py-2 font-semibold text-[#154d73] underline" :to="`/flaechen/${polygon.slug}`">
        {{ polygon.floor ? `${polygon.floor} – ` : '' }}{{ polygon.name }}
      </NuxtLink>
    </div>

    <button v-if="auth.authenticated" class="page-button-primary mt-3 w-full" type="button" @click="importOpen = true">
      {{ feature.properties.stadtplaner?.length ? 'Weitere Fläche anlegen' : 'Als Fläche übernehmen' }}
    </button>
    <div class="mt-3 border-t border-slate-200 pt-3">
      <OsmContributeAction
        :latitude="detail?.centroid?.latitude"
        :longitude="detail?.centroid?.longitude"
        :zoom="feature.properties.feature_type === 'point' ? 19 : 18"
        :vacant="isVacant"
      />
    </div>
    <p class="mt-2 text-[10px] text-slate-500">Daten: © OpenStreetMap-Mitwirkende</p>
    <OsmImportDialog v-if="auth.authenticated" v-model:open="importOpen" :feature="feature" :detail="detail" />
  </section>
</template>

<script setup lang="ts">
import { LoaderCircle, X } from 'lucide-vue-next'
import { osmCategoryLabels } from '~/utils/osmCategories'
import { getIndustryLabel } from '~/utils/industries'
import { osmObjectTags, safeOsmWebsite } from '~/utils/osm'
import { formatOsmCategory, formatOsmTag, localizedOsmName, osmDetailKeys } from '~/utils/osmTranslations'

const osm = useOsmViewportStore()
const auth = useAuthStore()
const mapSelection = useMapSelection()
const mapStore = useMapStore()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const embedded = computed(() => props.embedded)
const importOpen = ref(false)
const feature = computed(() => osm.selectedFeature)
const detail = computed(() => osm.detail)
const detailTags = computed(() => detail.value ? osmObjectTags(detail.value) : {})
const displayName = computed(() => localizedOsmName(detailTags.value, detail.value?.name || feature.value?.properties.name))
const detailCategory = computed(() => formatOsmCategory(detailTags.value))
const localizedDetails = computed(() => osmDetailKeys
  .map(key => formatOsmTag(key, detailTags.value[key], detailTags.value))
  .filter((item): item is NonNullable<typeof item> => item !== null))
const categoryLabel = computed(() => feature.value?.properties.canonical_category
  ? getIndustryLabel(feature.value.properties.canonical_category)
  : feature.value ? osmCategoryLabels[feature.value.properties.category] : '')
const typeLabel = computed(() => detail.value
  ? detailCategory.value.value
  : categoryLabel.value || (feature.value?.properties.feature_type === 'point' ? 'Ort oder Einrichtung' : 'Flächenobjekt'))
const isVacant = computed(() => detail.value?.occupancy_status === 'VACANT' || feature.value?.properties.occupancy_status === 'VACANT')
const address = computed(() => {
  const value = detail.value?.address
  if (!value) return ''
  return [[value.street, value.house_number].filter(Boolean).join(' '), [value.postal_code, value.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')
})
const osmUrl = computed(() => `https://www.openstreetmap.org/${feature.value?.properties.osm_type}/${feature.value?.properties.osm_id}`)
const safeWebsite = computed(() => safeOsmWebsite(detail.value?.website))

function closeSelection() {
  mapSelection.clearSelection()
  mapStore.closeGisPanels()
}
</script>
