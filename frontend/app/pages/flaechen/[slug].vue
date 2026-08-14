<template>
  <article class="bg-slate-50 py-8 sm:py-12">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
    <PageBreadcrumbs :items="[{ label: 'Karte', to: '/' }, { label: polygonData.name }]" />

    <div v-if="canEditPublicFields || canEditVerwaltung" class="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <span class="text-sm font-semibold" :class="saveStatusClass">{{ saveStatusLabel }}</span>
      <button v-if="autosaveStatus === 'error' || autosaveStatus === 'conflict'" type="button" class="text-sm font-bold text-[#154d73] underline" @click="autosave.retry()">
        Erneut versuchen
      </button>
    </div>
    <p v-if="autosaveStatus === 'conflict'" class="mt-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
      Die Fläche wurde zwischenzeitlich von jemand anderem geändert. Bitte lade die Seite neu, bevor du erneut speicherst.
    </p>

    <header class="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div class="h-1.5" :style="{ backgroundColor: categoryColor }" />
      <div class="p-5 sm:p-8">
        <PolygonCategoryBadge :category="polygonData.category" />
        <h1 v-if="canEditPublicFields" class="sr-only">{{ polygonData.name }}</h1>
        <label v-if="canEditPublicFields" class="mt-5 block max-w-3xl">
          <span class="field-label">Titel</span>
          <input v-model="polygonData.name" class="field-input text-2xl font-black sm:text-3xl" maxlength="160" @input="autosave.schedulePublic({ name: polygonData.name })">
        </label>
        <h1 v-else class="mt-5 break-words text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">{{ polygonData.name }}</h1>
        <p class="mt-3 flex items-start gap-2 text-base text-slate-600"><MapPin class="mt-0.5 size-5 shrink-0" aria-hidden="true" />{{ publicAddress }}</p>

        <dl class="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <PolygonMetricCard label="Fläche" :value="`${formatMetric(polygonData.area_m2)} m²`" :icon="Ruler" />
          <PolygonMetricCard label="Etage" :value="polygonData.floor || 'Nicht angegeben'" :icon="Layers3" />
          <PolygonMetricCard label="Kategorie" :value="categoryLabel" :icon="Tags" />
          <PolygonMetricCard label="Umfang" :value="`${formatMetric(polygonData.perimeter_m)} m`" :icon="RouteIcon" />
          <PolygonMetricCard label="Status" :value="occupancyLabel" :icon="CircleDot" />
          <PolygonMetricCard label="Betriebsform" :value="businessStructureLabel" :icon="Store" />
        </dl>
      </div>
    </header>

    <div class="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.8fr)]">
      <PolygonDetailMap
        :geometry="polygonData.geometry"
        :bbox="polygonData.bbox"
        :editable="canEditPublicFields"
        :color="categoryColor"
        @geometry-complete="saveGeometry"
      />

      <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="polygon-details">
        <h2 id="polygon-details" class="text-lg font-bold text-slate-950">Details</h2>
        <dl class="mt-5 space-y-5 text-sm">
          <div>
            <dt class="font-semibold text-slate-500">Kategorie</dt>
            <dd v-if="!canEditPublicFields" class="mt-1 text-slate-950">{{ categoryLabel }}</dd>
            <dd v-else class="mt-1">
            <select v-model="polygonData.category" class="field-input" @change="autosave.schedulePublic({ category: polygonData.category }, true)">
              <option v-for="industry in industries" :key="industry.key" :value="industry.key">{{ industry.label }}</option>
            </select>
            </dd>
          </div>
          <div>
            <dt class="font-semibold text-slate-500">Etage</dt>
            <dd v-if="!canEditPublicFields" class="mt-1 text-slate-950">{{ polygonData.floor || 'Nicht angegeben' }}</dd>
            <dd v-else class="mt-1">
            <select v-model="polygonData.floor" class="field-input" @change="autosave.schedulePublic({ floor: polygonData.floor || null }, true)">
              <option :value="null">Nicht angegeben</option>
              <option v-for="floor in floors" :key="floor" :value="floor">{{ floor }}</option>
            </select>
            </dd>
          </div>
          <div>
            <dt class="font-semibold text-slate-500">Größenklasse</dt>
            <dd v-if="!canEditPublicFields" class="mt-1 text-slate-950">{{ polygonData.area_size || 'Nicht angegeben' }}</dd>
            <dd v-else class="mt-1">
            <select v-model="polygonData.area_size" class="field-input" @change="autosave.schedulePublic({ area_size: polygonData.area_size || null }, true)">
              <option :value="null">Nicht angegeben</option>
              <option v-for="size in areaSizes" :key="size" :value="size">{{ size }}</option>
            </select>
            </dd>
          </div>
          <div>
            <dt class="font-semibold text-slate-500">Adresse</dt>
            <dd class="mt-1 leading-6 text-slate-950">{{ publicAddress }}</dd>
            <dd class="mt-1 text-xs leading-5 text-slate-500">Automatisch aus einem Punkt innerhalb der Fläche ermittelt.</dd>
          </div>
        </dl>
        <p v-if="polygonData.address_lookup_status === 'failed'" class="mt-5 rounded-xl bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">Daten gespeichert. Die Adresse konnte momentan nicht aktualisiert werden.</p>
      </section>
    </div>

    <section class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="polygon-description">
      <h2 id="polygon-description" class="text-lg font-bold text-slate-950">Beschreibung</h2>
      <label v-if="canEditPublicFields" class="mt-4 block"><span class="sr-only">Beschreibung</span><textarea v-model="polygonData.description" class="field-input min-h-36" placeholder="Öffentliche Beschreibung der Fläche" @input="autosave.schedulePublic({ description: polygonData.description || null })" /></label>
      <p v-else-if="polygonData.description" class="mt-4 whitespace-pre-line leading-7 text-slate-700">{{ polygonData.description }}</p>
      <p v-else class="mt-4 text-slate-500">Für diese Fläche ist noch keine Beschreibung hinterlegt.</p>
    </section>

    <PolygonOsmInfo class="mt-8 rounded-2xl shadow-sm" :info="osm.data.value" :loading="osm.loading.value" :error="osm.error.value" @retry="osm.retry" />

    <section v-if="polygonData.osm_sources.length" class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="osm-origin">
      <h2 id="osm-origin" class="text-lg font-bold text-slate-950">Datenherkunft</h2>
      <p class="mt-2 text-sm text-slate-600">Diese Stadtplanner-Fläche wurde aus öffentlichen OpenStreetMap-Referenzdaten angelegt. Ihre Geometrie und Fachangaben können in Stadtplanner unabhängig weiterbearbeitet werden.</p>
      <ul class="mt-4 space-y-2 text-sm">
        <li v-for="source in polygonData.osm_sources" :key="`${source.osm_type}-${source.osm_id}`" class="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-4 py-3">
          <span>OSM {{ source.osm_type }} {{ source.osm_id }} · übernommen am {{ formatDate(source.imported_at) }}</span>
          <a class="font-bold text-[#154d73] underline" :href="getOsmObjectUrl(source.osm_type, source.osm_id) || undefined" target="_blank" rel="noopener noreferrer">Auf OpenStreetMap ansehen</a>
        </li>
      </ul>
    </section>

    <LocationAnalysis class="mt-8" :slug="slug" />
    <ComparableList class="mt-8" :slug="slug" />

    <PolygonManagementForm
      v-if="verwaltungData && canViewVerwaltung"
      v-model="verwaltungData"
      class="mt-8"
      @change="scheduleManagement"
    />

    <PolygonDeleteSection v-if="canDelete" class="mt-8" :name="polygonData.name" :loading="deleting" :error="deleteError" @confirm="removePolygon" />

    <p class="mt-8 text-sm text-[#687176]">Zuletzt aktualisiert: {{ formatDate(polygonData.updated_at) }}</p>
    </div>
  </article>
</template>

<script setup lang="ts">
import { CircleDot, Layers3, MapPin, Route as RouteIcon, Ruler, Store, Tags } from 'lucide-vue-next'
import type { AreaGeometry, PolygonEditorDetail, PolygonVerwaltungDetail, PublicPolygonDetail } from '~/types/geo'
import { getIndustryColor, getIndustryLabel, industries } from '~/utils/industries'
import { getOsmObjectUrl } from '~/utils/osmLinks'

const route = useRoute()
const slugParam = Array.isArray(route.params.slug) ? route.params.slug[0] : route.params.slug
if (typeof slugParam !== 'string' || !slugParam) {
  throw createError({ statusCode: 404, statusMessage: 'Fläche nicht gefunden' })
}
const slug = slugParam
const polygonApi = usePolygonApi()
const authStore = useAuthStore()
const { data: polygon } = await useAsyncData(`polygon-${slug}`, async () => {
  try {
    return await polygonApi.bySlug(slug)
  } catch (error) {
    const statusCode = typeof error === 'object' && error && 'statusCode' in error ? Number(error.statusCode) : 500
    throw createError({
      statusCode: statusCode === 404 ? 404 : 500,
      statusMessage: statusCode === 404 ? 'Fläche nicht gefunden' : 'Fläche konnte nicht geladen werden'
    })
  }
})
if (!polygon.value) throw createError({ statusCode: 404, statusMessage: 'Fläche nicht gefunden' })

const polygonData = ref<PublicPolygonDetail>({ ...polygon.value })
const osm = usePolygonOsmInfo()
const editorData = ref<PolygonEditorDetail | null>(null)
const verwaltungData = ref<PolygonVerwaltungDetail | null>(null)
const updatedAt = ref(polygonData.value.updated_at)
const { canEditPublicFields, canDelete, canViewVerwaltung, canEditVerwaltung } = usePolygonPermissions(editorData)
usePolygonSeo(polygonData)
const deleting = ref(false)
const deleteError = ref('')

const autosave = usePolygonAutosave({
  updatedAt,
  async savePublic(changes) {
    const response = await polygonApi.update(polygonData.value.id, changes)
    polygonData.value = { ...polygonData.value, ...pickPublicUpdate(response) }
    return response
  },
  async saveVerwaltung(changes) {
    const response = await polygonApi.updateVerwaltung(polygonData.value.id, changes)
    verwaltungData.value = response
    polygonData.value.updated_at = response.updated_at
    return response
  },
  async onSaved(kind, _response, changes) {
    if (kind !== 'public' || !('geometry' in changes)) return
    const refreshed = await polygonApi.bySlug(slug)
    polygonData.value = {
      ...polygonData.value,
      geometry: refreshed.geometry,
      address_display_name: refreshed.address_display_name,
      address_street: refreshed.address_street,
      address_house_number: refreshed.address_house_number,
      address_postal_code: refreshed.address_postal_code,
      address_city: refreshed.address_city,
      address_country: refreshed.address_country,
      address_lookup_status: refreshed.address_lookup_status,
      area_m2: refreshed.area_m2,
      perimeter_m: refreshed.perimeter_m,
      centroid: refreshed.centroid,
      bbox: refreshed.bbox,
      updated_at: refreshed.updated_at
    }
    updatedAt.value = refreshed.updated_at
    void osm.loadBySlug({ id: refreshed.id, slug: refreshed.slug, updatedAt: refreshed.updated_at }, true)
  }
})

onMounted(async () => {
  void osm.loadBySlug({ id: polygonData.value.id, slug, updatedAt: polygonData.value.updated_at })
  await authStore.initialize()
  if (!authStore.user) return
  try {
    editorData.value = await polygonApi.editor(polygonData.value.id)
    updatedAt.value = editorData.value.updated_at
  } catch {
    editorData.value = null
  }
  if (canViewVerwaltung.value) {
    try {
      verwaltungData.value = await polygonApi.verwaltung(polygonData.value.id)
      updatedAt.value = verwaltungData.value.updated_at
    } catch {
      verwaltungData.value = null
    }
  }
})

const floors = ['UG', 'EG', '1OG', '2OG', '3OG', 'DG']
const areaSizes = ['S', 'M', 'L', 'XL'] as const
const autosaveStatus = autosave.status
const categoryLabel = computed(() => getIndustryLabel(polygonData.value.category))
const categoryColor = computed(() => getIndustryColor(polygonData.value.category))
const occupancyLabel = computed(() => ({ OCCUPIED: 'Belegt', VACANT: 'Leerstehend', UNKNOWN: 'Unbekannt' }[polygonData.value.occupancy_status]))
const businessStructureLabel = computed(() => ({ CHAIN: 'Filialist', INDEPENDENT: 'Inhabergeführt', UNKNOWN: 'Unbekannt' }[polygonData.value.business_structure]))
const publicAddress = computed(() => polygonData.value.address_display_name || [
  [polygonData.value.address_street, polygonData.value.address_house_number].filter(Boolean).join(' '),
  [polygonData.value.address_postal_code, polygonData.value.address_city].filter(Boolean).join(' '),
  polygonData.value.address_country
].filter(Boolean).join(', ') || 'Noch keine Adresse ermittelt')
const saveStatusLabel = computed(() => ({
  saved: '● Gespeichert', dirty: '● Nicht gespeichert', saving: '● Speichert …', error: '● Fehler beim Speichern', conflict: '● Versionskonflikt'
}[autosaveStatus.value]))
const saveStatusClass = computed(() => autosaveStatus.value === 'saved' ? 'text-emerald-700' : autosaveStatus.value === 'saving' ? 'text-[#154d73]' : 'text-amber-700')

function saveGeometry(geometry: AreaGeometry) {
  polygonData.value.geometry = geometry
  autosave.schedulePublic({ geometry }, true)
}

function scheduleManagement(field: keyof PolygonVerwaltungDetail, value: unknown) {
  if (canEditVerwaltung.value) autosave.scheduleVerwaltung({ [field]: value })
}

async function removePolygon() {
  if (deleting.value) return
  if (autosaveStatus.value === 'dirty' || autosaveStatus.value === 'saving') {
    deleteError.value = 'Bitte warten Sie, bis die laufenden Änderungen gespeichert sind.'
    return
  }
  deleting.value = true
  deleteError.value = ''
  try {
    await polygonApi.remove(polygonData.value.id)
    clearNuxtData(`polygon-${slug}`)
    await navigateTo('/')
  } catch (cause) {
    deleteError.value = cause instanceof Error ? cause.message : 'Die Fläche konnte nicht gelöscht werden.'
  } finally {
    deleting.value = false
  }
}

function pickPublicUpdate(response: { name: string, description?: string | null, floor?: string | null, category: string, geometry: AreaGeometry, properties?: Record<string, unknown>, updated_at: string }) {
  const size = response.properties?.size
  const areaSize = areaSizes.includes(size as typeof areaSizes[number]) ? size as typeof areaSizes[number] : null
  return { name: response.name, description: response.description, floor: response.floor, area_size: areaSize, category: response.category, geometry: response.geometry, updated_at: response.updated_at }
}

function formatMetric(value: number) { return Math.round(value).toLocaleString('de-DE') }
function formatDate(value: string) { return new Intl.DateTimeFormat('de-DE').format(new Date(value)) }
</script>
