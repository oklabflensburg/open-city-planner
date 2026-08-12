<template>
  <Card v-if="polygon" class="p-4">
    <div class="mb-3 flex items-center justify-between">
      <div>
        <h2 class="text-[12px] font-semibold uppercase text-[#3f4448]">Fläche</h2>
        <p class="text-sm font-semibold text-[#202427]">{{ polygon.name }}</p>
      </div>
      <button class="rounded-md p-2 text-[#8b9298] hover:bg-[#f4f4f4]" type="button" aria-label="Auswahl schließen" @click="closeSelection">
        <X class="size-4" />
      </button>
    </div>
    <dl class="grid grid-cols-2 gap-3 text-[12px]">
      <div>
        <dt class="text-[#777d82]">Flächentyp</dt>
        <dd class="font-semibold">{{ selectedIndustryLabel }}</dd>
      </div>
      <div>
        <dt class="text-[#777d82]">Größe</dt>
        <dd class="font-semibold">{{ selectedSize }}</dd>
      </div>
      <div>
        <dt class="text-[#777d82]">Etage</dt>
        <dd class="font-semibold">{{ selectedFloor }}</dd>
      </div>
      <div>
        <dt class="text-[#777d82]">Status</dt>
        <dd class="font-semibold">{{ status }}</dd>
      </div>
      <div v-if="store.selectedMetrics">
        <dt class="text-[#777d82]">Fläche</dt>
        <dd class="font-semibold">{{ Math.round(store.selectedMetrics.area_m2).toLocaleString('de-DE') }} m²</dd>
      </div>
      <div v-if="store.selectedMetrics">
        <dt class="text-[#777d82]">Umfang</dt>
        <dd class="font-semibold">{{ Math.round(store.selectedMetrics.perimeter_m).toLocaleString('de-DE') }} m</dd>
      </div>
    </dl>
    <NuxtLink
      class="mt-4 inline-flex min-h-10 items-center rounded-md font-semibold text-[#154d73] hover:underline"
      :to="`/flaechen/${polygon.slug}`"
    >
      Details anzeigen
    </NuxtLink>
    <div v-if="isEditing" class="mt-4 space-y-4 border-t border-[#ececec] pt-4">
      <div>
        <p class="mb-2 text-[12px] font-semibold uppercase text-[#3f4448]">Flächentyp</p>
        <div class="grid gap-1">
          <button
            v-for="industry in industries"
            :key="industry.key"
            class="flex min-h-9 items-center gap-2 rounded-md px-2 text-left text-xs font-semibold text-[#303438] transition hover:bg-[#f3f3f3] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="{ 'bg-[#edf4f8] text-[#154d73] shadow-sm': draftCategory === industry.key }"
            type="button"
            @click="selectCategory(industry.key)"
          >
            <span class="size-3 shrink-0 rounded-full" :style="{ backgroundColor: industryColors[industry.key] }" />
            {{ industry.label }}
          </button>
        </div>
      </div>
      <div>
        <p class="mb-2 text-[12px] font-semibold uppercase text-[#3f4448]">Größe</p>
        <div class="grid grid-cols-4 gap-1">
          <button
            v-for="size in sizes"
            :key="size"
            class="min-h-9 rounded-md text-xs font-bold text-[#767d83] transition hover:bg-[#f3f3f3] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="{ 'bg-[#edf4f8] text-[#154d73] shadow-sm': draftSize === size }"
            type="button"
            @click="draftSize = size"
          >
            {{ size }}
          </button>
        </div>
      </div>
      <div>
        <p class="mb-2 text-[12px] font-semibold uppercase text-[#3f4448]">Etage</p>
        <div class="grid grid-cols-3 gap-1">
          <button
            v-for="floor in floors"
            :key="floor"
            class="min-h-9 rounded-md text-xs font-bold text-[#767d83] transition hover:bg-[#f3f3f3] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="{ 'bg-[#edf4f8] text-[#154d73] shadow-sm': draftFloor === floor }"
            type="button"
            @click="draftFloor = floor"
          >
            {{ floor }}
          </button>
        </div>
      </div>
    </div>
    <div class="mt-4 flex gap-2">
      <Button :active="isEditing" @click="startEditing"><Pencil class="size-4" />Bearbeiten</Button>
      <Button :disabled="store.saving" @click="save"><Save class="size-4" />Speichern</Button>
      <Button @click="remove"><Trash2 class="size-4" />Löschen</Button>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { Pencil, Save, Trash2, X } from 'lucide-vue-next'
import { industries, industryColors, type IndustryKey } from '~/utils/industries'

type SizeKey = 'S' | 'M' | 'L' | 'XL'
type FloorKey = 'UG' | 'EG' | 'OG'

const store = usePolygonStore()
const mapStore = useMapStore()
const polygon = computed(() => store.selectedPolygon)
const status = computed(() => (store.saveState === 'saving' ? 'Speichert...' : store.saveState === 'error' ? 'Fehler' : 'Gespeichert'))
const sizes = ['S', 'M', 'L', 'XL'] as const
const floors = ['UG', 'EG', 'OG'] as const
const draftCategory = ref<IndustryKey>('otherAreas')
const draftSize = ref<SizeKey>('M')
const draftFloor = ref<FloorKey>('EG')
const isEditing = computed(() => mapStore.activeMode === 'edit')
const selectedIndustryLabel = computed(() => industries.find((industry) => industry.key === draftCategory.value)?.label || draftCategory.value)
const selectedSize = computed(() => draftSize.value)
const selectedFloor = computed(() => draftFloor.value)

watch(polygon, syncDraftFromPolygon, { immediate: true })

function syncDraftFromPolygon() {
  if (!polygon.value) return
  const category = polygon.value.category
  draftCategory.value = industries.some((industry) => industry.key === category) ? category as IndustryKey : 'otherAreas'
  draftSize.value = toSize(polygon.value.properties.size)
  draftFloor.value = toFloor(polygon.value.properties.floor)
}

function toSize(value: unknown): SizeKey {
  return sizes.includes(value as SizeKey) ? value as SizeKey : 'M'
}

function toFloor(value: unknown): FloorKey {
  return floors.includes(value as FloorKey) ? value as FloorKey : 'EG'
}

function selectCategory(category: IndustryKey) {
  draftCategory.value = category
  if (!polygon.value) return
  store.polygons = store.polygons.map((item) => (
    item.id === polygon.value?.id ? { ...item, category } : item
  ))
}

const startEditing = () => {
  syncDraftFromPolygon()
  mapStore.setMode('edit')
}

const save = async () => {
  if (polygon.value) {
    await store.updatePolygon(polygon.value.id, {
      category: draftCategory.value,
      geometry: polygon.value.geometry,
      properties: {
        ...polygon.value.properties,
        size: draftSize.value,
        floor: draftFloor.value
      }
    })
  }
}

const remove = async () => {
  if (polygon.value) {
    await store.deletePolygon(polygon.value.id)
  }
}

function closeSelection() {
  mapStore.setMode('select')
  store.clearSelection()
  mapStore.analysisDrawerOpen = false
}
</script>
