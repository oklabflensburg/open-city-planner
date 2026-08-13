<template>
  <article class="mx-auto max-w-5xl px-5 py-12 sm:px-6 lg:px-8">
    <nav class="text-sm text-[#687176]" aria-label="Brotkrümelnavigation">
      <ol class="flex flex-wrap items-center gap-2">
        <li><NuxtLink class="font-semibold text-[#154d73]" to="/">Karte</NuxtLink></li>
        <li aria-hidden="true">/</li>
        <li aria-current="page">{{ polygonData.name }}</li>
      </ol>
    </nav>

    <div v-if="canEditPublicFields || canEditVerwaltung" class="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#dfe4e6] bg-white px-4 py-3">
      <span class="text-sm font-semibold" :class="saveStatusClass">{{ saveStatusLabel }}</span>
      <button v-if="autosaveStatus === 'error' || autosaveStatus === 'conflict'" type="button" class="text-sm font-bold text-[#154d73] underline" @click="autosave.retry()">
        Erneut versuchen
      </button>
    </div>
    <p v-if="autosaveStatus === 'conflict'" class="mt-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
      Die Fläche wurde zwischenzeitlich von jemand anderem geändert. Bitte lade die Seite neu, bevor du erneut speicherst.
    </p>

    <header class="mt-6 max-w-3xl">
      <p class="text-xs font-bold uppercase tracking-wide text-[#687176]">Öffentliche Fläche</p>
      <template v-if="canEditPublicFields">
        <label class="mt-3 block">
          <span class="field-label">Titel</span>
          <input v-model="polygonData.name" class="field-input text-xl font-bold" maxlength="160" @input="autosave.schedulePublic({ name: polygonData.name })">
        </label>
        <label class="mt-4 block">
          <span class="field-label">Beschreibung</span>
          <textarea v-model="polygonData.description" class="field-input min-h-32" @input="autosave.schedulePublic({ description: polygonData.description || null })" />
        </label>
      </template>
      <template v-else>
        <h1 class="mt-2 text-3xl font-bold text-[#202427]">{{ polygonData.name }}</h1>
        <p v-if="polygonData.description" class="mt-4 text-base leading-7 text-[#4f575c]">{{ polygonData.description }}</p>
      </template>
    </header>

    <section class="mt-8 rounded-xl border border-[#dfe4e6] bg-white p-6" aria-labelledby="polygon-details">
      <h2 id="polygon-details" class="text-lg font-bold text-[#202427]">Flächendaten</h2>
      <dl class="mt-5 grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt class="font-semibold text-[#687176]">Kategorie</dt>
          <dd v-if="!canEditPublicFields" class="mt-1 text-[#202427]">{{ categoryLabel }}</dd>
          <dd v-else class="mt-1">
            <select v-model="polygonData.category" class="field-input" @change="autosave.schedulePublic({ category: polygonData.category }, true)">
              <option v-for="industry in industries" :key="industry.key" :value="industry.key">{{ industry.label }}</option>
            </select>
          </dd>
        </div>
        <div>
          <dt class="font-semibold text-[#687176]">Etage</dt>
          <dd v-if="!canEditPublicFields" class="mt-1 text-[#202427]">{{ polygonData.floor || 'Nicht angegeben' }}</dd>
          <dd v-else class="mt-1">
            <select v-model="polygonData.floor" class="field-input" @change="autosave.schedulePublic({ floor: polygonData.floor || null }, true)">
              <option :value="null">Nicht angegeben</option>
              <option v-for="floor in floors" :key="floor" :value="floor">{{ floor }}</option>
            </select>
          </dd>
        </div>
        <div>
          <dt class="font-semibold text-[#687176]">Größenklasse</dt>
          <dd v-if="!canEditPublicFields" class="mt-1 text-[#202427]">{{ polygonData.area_size || 'Nicht angegeben' }}</dd>
          <dd v-else class="mt-1">
            <select v-model="polygonData.area_size" class="field-input" @change="autosave.schedulePublic({ area_size: polygonData.area_size || null }, true)">
              <option :value="null">Nicht angegeben</option>
              <option v-for="size in areaSizes" :key="size" :value="size">{{ size }}</option>
            </select>
          </dd>
        </div>
        <div>
          <dt class="font-semibold text-[#687176]">Fläche</dt>
          <dd class="mt-1 text-[#202427]">{{ formatMetric(polygonData.area_m2) }} m²</dd>
        </div>
        <div>
          <dt class="font-semibold text-[#687176]">Umfang</dt>
          <dd class="mt-1 text-[#202427]">{{ formatMetric(polygonData.perimeter_m) }} m</dd>
        </div>
      </dl>
    </section>

    <section class="mt-8 rounded-xl border border-[#dfe4e6] bg-white p-6" aria-labelledby="polygon-location">
      <h2 id="polygon-location" class="text-lg font-bold text-[#202427]">Adresse</h2>
      <p class="mt-2 text-[#202427]">{{ publicAddress }}</p>
      <p class="mt-1 text-sm text-[#687176]">Automatisch aus einem Punkt innerhalb der Polygonfläche ermittelt.</p>
      <p v-if="polygonData.address_lookup_status === 'failed'" class="mt-3 text-sm font-semibold text-amber-700">
        Daten gespeichert. Die Adresse konnte momentan nicht aktualisiert werden.
      </p>
    </section>

    <PolygonOsmInfo class="mt-8" :info="osm.data.value" :loading="osm.loading.value" :error="osm.error.value" @retry="osm.retry" />

    <PolygonDetailMap
      class="mt-8"
      :geometry="polygonData.geometry"
      :bbox="polygonData.bbox"
      :editable="canEditPublicFields"
      @geometry-complete="saveGeometry"
    />

    <PolygonManagementForm
      v-if="verwaltungData && canViewVerwaltung"
      v-model="verwaltungData"
      class="mt-8"
      @change="scheduleManagement"
    />

    <p class="mt-8 text-sm text-[#687176]">Zuletzt aktualisiert: {{ formatDate(polygonData.updated_at) }}</p>
  </article>
</template>

<script setup lang="ts">
import type { PolygonEditorDetail, PolygonGeometry, PolygonVerwaltungDetail, PublicPolygonDetail } from '~/types/geo'
import { industries } from '~/utils/industries'

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
const { canEditPublicFields, canViewVerwaltung, canEditVerwaltung } = usePolygonPermissions(editorData)
usePolygonSeo(polygonData)

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
const categoryLabel = computed(() => industries.find(industry => industry.key === polygonData.value.category)?.label || polygonData.value.category || 'Nicht angegeben')
const publicAddress = computed(() => polygonData.value.address_display_name || [
  [polygonData.value.address_street, polygonData.value.address_house_number].filter(Boolean).join(' '),
  [polygonData.value.address_postal_code, polygonData.value.address_city].filter(Boolean).join(' '),
  polygonData.value.address_country
].filter(Boolean).join(', ') || 'Noch keine Adresse ermittelt')
const saveStatusLabel = computed(() => ({
  saved: '● Gespeichert', dirty: '● Nicht gespeichert', saving: '● Speichert …', error: '● Fehler beim Speichern', conflict: '● Versionskonflikt'
}[autosaveStatus.value]))
const saveStatusClass = computed(() => autosaveStatus.value === 'saved' ? 'text-emerald-700' : autosaveStatus.value === 'saving' ? 'text-[#154d73]' : 'text-amber-700')

function saveGeometry(geometry: PolygonGeometry) {
  polygonData.value.geometry = geometry
  autosave.schedulePublic({ geometry }, true)
}

function scheduleManagement(field: keyof PolygonVerwaltungDetail, value: unknown) {
  if (canEditVerwaltung.value) autosave.scheduleVerwaltung({ [field]: value })
}

function pickPublicUpdate(response: { name: string, description?: string | null, floor?: string | null, category: string, geometry: PolygonGeometry, properties?: Record<string, unknown>, updated_at: string }) {
  const size = response.properties?.size
  const areaSize = areaSizes.includes(size as typeof areaSizes[number]) ? size as typeof areaSizes[number] : null
  return { name: response.name, description: response.description, floor: response.floor, area_size: areaSize, category: response.category, geometry: response.geometry, updated_at: response.updated_at }
}

function formatMetric(value: number) { return Math.round(value).toLocaleString('de-DE') }
function formatDate(value: string) { return new Intl.DateTimeFormat('de-DE').format(new Date(value)) }
</script>

<style scoped>
.field-label { display: block; margin-bottom: 0.35rem; font-size: 0.8rem; font-weight: 700; color: #4f575c; }
.field-input { min-height: 2.75rem; width: 100%; border: 1px solid #cfd6d9; border-radius: 0.45rem; background: white; padding: 0.6rem 0.75rem; color: #202427; }
.field-input:focus { border-color: #154d73; outline: 2px solid rgb(21 77 115 / 18%); outline-offset: 1px; }
</style>
