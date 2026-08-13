<template>
  <div class="relative h-full min-h-0 min-w-0 overflow-hidden rounded-2xl border border-white bg-slate-100 shadow-[0_1px_12px_rgba(20,24,28,0.08)] lg:min-h-[420px]">
    <div ref="mapEl" class="absolute inset-0 h-full w-full" />
    <div v-if="!mapStore.mapLoaded && !mapError" class="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-slate-100/90" role="status" aria-live="polite">
      <div class="flex items-center gap-3 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">
        <LoaderCircle class="size-5 animate-spin text-[#154d73]" aria-hidden="true" />
        Karte wird geladen …
      </div>
    </div>
    <div class="pointer-events-none absolute left-3 top-3 z-10">
      <MapControls @zoom-in="map?.zoomIn()" @zoom-out="map?.zoomOut()" @reset="resetView" />
    </div>
    <div class="pointer-events-none absolute right-3 top-3 z-10">
      <MapLayerControl @toggle-polygons="setPolygonVisibility" />
    </div>
    <div class="pointer-events-none absolute bottom-3 left-1/2 z-10 hidden -translate-x-1/2 lg:block">
      <div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/95 px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-lg backdrop-blur">
        <MousePointer2 class="size-4 text-[#154d73]" aria-hidden="true" />
        Klicken Sie auf ein Polygon, um Details zu sehen.
      </div>
    </div>
    <div v-if="mapError" class="absolute inset-x-3 top-1/2 z-30 mx-auto max-w-sm -translate-y-1/2 rounded-xl border border-rose-200 bg-white p-4 text-center shadow-xl" role="alert">
      <p class="text-sm font-bold text-rose-800">Karte konnte nicht geladen werden.</p>
      <p class="mt-1 break-words text-xs leading-5 text-slate-600">{{ mapError }}</p>
      <button class="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#154d73] px-4 text-sm font-bold text-white" type="button" @click="retryMap">
        <RefreshCw class="size-4" aria-hidden="true" /> Erneut versuchen
      </button>
    </div>
    <div v-else-if="polygonStore.error" class="absolute bottom-24 left-3 z-10 max-w-[calc(100%-1.5rem)] rounded-lg bg-white px-3 py-2 text-xs text-red-700 shadow lg:bottom-16 lg:max-w-[320px]">
      {{ polygonStore.error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FeatureCollection } from 'geojson'
import type { GeoJSONSource, Map, MapLayerMouseEvent } from 'maplibre-gl'
import { LoaderCircle, MousePointer2, RefreshCw } from 'lucide-vue-next'
import { industryColorExpression } from '~/utils/industries'

const config = useRuntimeConfig()
const mapStore = useMapStore()
const polygonStore = usePolygonStore()
const filterStore = useFilterStore()
const route = useRoute()
const mapEl = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const mapError = ref('')
const hoveredPolygonId = ref<string | null>(null)
const initialCenter: [number, number] = [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)]
const initialZoom = Number(config.public.mapZoom)
let disposed = false

const visibleFeatureCollection = computed<FeatureCollection>(() => ({
  type: 'FeatureCollection',
  features: polygonStore.featureCollection.features.filter(feature => (
    filterStore.activeCategories.includes(feature.properties.category as never)
    && normalizeSize(feature.properties.size) === filterStore.selectedSize
    && normalizeFloor(feature.properties.floor) === filterStore.selectedFloor
  ))
}))

onMounted(async () => {
  if (!mapEl.value) return
  mapStore.mapLoaded = false
  mapStore.center = initialCenter
  mapStore.zoom = initialZoom
  try {
    const maplibregl = await import('maplibre-gl')
    const container = mapEl.value
    if (disposed || !container?.isConnected) return
    const instance = new maplibregl.Map({
      container,
      style: String(config.public.versatilesStyleUrl),
      center: initialCenter,
      zoom: initialZoom,
      bearing: 0,
      pitch: 0,
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'low-power' }
    })
    map.value = instance
    instance.touchZoomRotate.enable()
    instance.dragRotate.enable()
    instance.on('load', async () => {
      await polygonStore.loadPolygons()
      addPolygonLayers(instance)
      const requested = typeof route.query.polygon === 'string' ? route.query.polygon : ''
      if (requested && polygonStore.polygons.some(polygon => polygon.id === requested)) {
        await selectPolygon(requested)
      }
      mapStore.mapLoaded = true
      mapError.value = ''
      requestAnimationFrame(() => instance.resize())
    })
    instance.on('click', 'overview-polygons-fill', (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id
      if (id) void selectPolygon(String(id))
    })
    instance.on('mouseenter', 'overview-polygons-fill', (event: MapLayerMouseEvent) => {
      instance.getCanvas().style.cursor = 'pointer'
      hoveredPolygonId.value = String(event.features?.[0]?.properties?.id || '') || null
      applyFeatureStyles()
    })
    instance.on('mousemove', 'overview-polygons-fill', (event: MapLayerMouseEvent) => {
      hoveredPolygonId.value = String(event.features?.[0]?.properties?.id || '') || null
      applyFeatureStyles()
    })
    instance.on('mouseleave', 'overview-polygons-fill', () => {
      instance.getCanvas().style.cursor = ''
      hoveredPolygonId.value = null
      applyFeatureStyles()
    })
    instance.on('moveend', () => mapStore.setView(
      [instance.getCenter().lng, instance.getCenter().lat],
      instance.getZoom(),
      instance.getBearing(),
      instance.getPitch()
    ))
    instance.on('error', (event) => {
      if (disposed) return
      console.warn('MapLibre resource error', event.error)
      if (!mapStore.mapLoaded) mapError.value = 'Die Kartenbasis konnte nicht vollständig geladen werden.'
    })
    instance.on('webglcontextlost', () => {
      if (!disposed) mapError.value = 'Der Grafik-Kontext wurde unterbrochen. Die Kartenanzeige wird wiederhergestellt.'
    })
    instance.on('webglcontextrestored', () => {
      if (!disposed) mapError.value = ''
    })
    window.addEventListener('resize', resizeMap)
    window.addEventListener('orientationchange', resizeAfterOrientationChange)
  } catch (error) {
    if (disposed) return
    mapError.value = error instanceof Error ? error.message : 'Die Kartenbibliothek konnte nicht geladen werden.'
  }
})

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', resizeMap)
  window.removeEventListener('orientationchange', resizeAfterOrientationChange)
  map.value?.remove()
  map.value = null
})

watch(visibleFeatureCollection, collection => updateSource(collection), { deep: true })
watch(() => polygonStore.selectedPolygonId, applyFeatureStyles)
watch(() => mapStore.categoryHighlight, applyFeatureStyles)

function addPolygonLayers(instance: Map) {
  instance.addSource('overview-polygons', { type: 'geojson', data: visibleFeatureCollection.value })
  instance.addLayer({
    id: 'overview-polygons-fill',
    type: 'fill',
    source: 'overview-polygons',
    paint: { 'fill-color': categoryColorExpression(), 'fill-opacity': 0.3 }
  })
  instance.addLayer({
    id: 'overview-polygons-line',
    type: 'line',
    source: 'overview-polygons',
    paint: { 'line-color': categoryColorExpression(), 'line-width': 2 }
  })
  applyFeatureStyles()
}

async function selectPolygon(id: string) {
  await polygonStore.selectPolygon(id)
  if (window.matchMedia('(max-width: 1023px)').matches) {
    mapStore.activeMobilePanel = null
    mapStore.polygonPreviewOpen = true
  }
  const bbox = polygonStore.selectedMetrics?.bbox
  if (bbox && map.value) map.value.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 72, maxZoom: 18 })
}

function applyFeatureStyles() {
  if (!map.value?.getLayer('overview-polygons-fill')) return
  const selected = polygonStore.selectedPolygonId || ''
  const hovered = hoveredPolygonId.value || ''
  const highlighted = mapStore.categoryHighlight || ''
  map.value.setPaintProperty('overview-polygons-fill', 'fill-opacity', [
    'case',
    ['==', ['get', 'id'], selected], 0.55,
    ['==', ['get', 'id'], hovered], 0.46,
    ['==', ['get', 'category'], highlighted], 0.5,
    0.3
  ])
  map.value.setPaintProperty('overview-polygons-line', 'line-color', [
    'case', ['==', ['get', 'id'], selected], '#0f172a', categoryColorExpression()
  ])
  map.value.setPaintProperty('overview-polygons-line', 'line-width', [
    'case', ['==', ['get', 'id'], selected], 3.5, ['==', ['get', 'id'], hovered], 3, 2
  ])
}

function categoryColorExpression() { return industryColorExpression() as any }

function normalizeSize(value: unknown) {
  return ['S', 'M', 'L', 'XL'].includes(String(value)) ? String(value) : 'M'
}

function normalizeFloor(value: unknown) {
  return ['UG', 'EG', 'OG'].includes(String(value)) ? String(value) : 'EG'
}

function updateSource(data: FeatureCollection) {
  const source = map.value?.getSource('overview-polygons') as GeoJSONSource | undefined
  source?.setData(data)
}

function setPolygonVisibility(visible: boolean) {
  if (!map.value) return
  const visibility = visible ? 'visible' : 'none'
  map.value.setLayoutProperty('overview-polygons-fill', 'visibility', visibility)
  map.value.setLayoutProperty('overview-polygons-line', 'visibility', visibility)
}

function resetView() {
  map.value?.easeTo({ center: initialCenter, zoom: initialZoom, bearing: 0, pitch: 0 })
}

function resizeMap() {
  map.value?.resize()
}

function resizeAfterOrientationChange() {
  window.setTimeout(resizeMap, 180)
}

function retryMap() {
  window.location.reload()
}
</script>
