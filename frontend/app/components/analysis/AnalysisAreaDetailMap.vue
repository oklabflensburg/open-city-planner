<template>
  <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-labelledby="area-map-title">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:px-5">
      <h2 id="area-map-title" class="text-lg font-bold text-slate-950">Gebietskarte</h2>
      <button class="min-h-11 cursor-pointer rounded-xl border border-slate-300 px-4 text-sm font-bold text-[#154d73] hover:bg-slate-50" type="button" @click="fitArea">Gebiet zentrieren</button>
    </div>
    <div class="relative">
      <div ref="mapElement" class="h-[clamp(300px,45dvh,500px)] w-full" role="img" :aria-label="`Karte des Gebiets ${area.name}`" />
      <p v-if="mapError" class="absolute inset-x-4 top-4 rounded-xl bg-white px-4 py-3 text-sm text-rose-700 shadow" role="alert">{{ mapError }}</p>
    </div>
    <p class="border-t border-slate-200 px-4 py-3 text-xs leading-5 text-slate-500">Gebietsgrenze und erfasste Stadtplaner-Flächen. Kartendaten © OpenStreetMap-Mitwirkende.</p>
  </section>
</template>

<script setup lang="ts">
import type { GeoJSONSource, Map } from 'maplibre-gl'
import type { PolygonFeatureCollection } from '~/types/geo'
import type { AnalysisAreaDetail } from '~/types/analysisArea'
import { loadMapStyle } from '~/config/mapStyles'
import { setMapCursor } from '~/utils/mapCursor'

const props = defineProps<{ area: AnalysisAreaDetail }>()
const emit = defineEmits<{ ready: [] }>()
const config = useRuntimeConfig()
const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const mapError = ref('')
let disposed = false
let mapDragging = false
let resizeObserver: ResizeObserver | null = null

onMounted(async () => {
  const container = mapElement.value
  if (!container) return
  try {
    const [{ default: maplibregl }, style, polygons] = await Promise.all([
      import('maplibre-gl'),
      loadMapStyle(String(config.public.mapStyleUrl || '')),
      useApi().request<PolygonFeatureCollection>('/polygons/geojson').catch(() => ({ type: 'FeatureCollection' as const, features: [] })),
      import('maplibre-gl/dist/maplibre-gl.css')
    ])
    if (disposed || !container.isConnected) return
    const instance = new maplibregl.Map({
      container,
      style,
      bounds: [[props.area.bbox[0], props.area.bbox[1]], [props.area.bbox[2], props.area.bbox[3]]],
      fitBoundsOptions: { padding: 42, maxZoom: 16 },
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'low-power' }
    })
    map.value = instance
    setMapCursor(instance, 'pan')
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    instance.on('dragstart', () => {
      mapDragging = true
      setMapCursor(instance, 'dragging')
    })
    instance.on('dragend', () => {
      mapDragging = false
      setMapCursor(instance, 'pan')
    })
    instance.on('load', () => {
      instance.addSource('area-detail-boundary', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: props.area.geometry } })
      instance.addLayer({ id: 'area-detail-fill', type: 'fill', source: 'area-detail-boundary', paint: { 'fill-color': '#154d73', 'fill-opacity': 0.12 } })
      instance.addLayer({ id: 'area-detail-line', type: 'line', source: 'area-detail-boundary', paint: { 'line-color': '#154d73', 'line-width': 3 } })
      instance.addSource('area-detail-polygons', { type: 'geojson', data: polygons })
      instance.addLayer({ id: 'area-detail-polygons-fill', type: 'fill', source: 'area-detail-polygons', paint: { 'fill-color': '#d97706', 'fill-opacity': 0.38 } })
      instance.addLayer({ id: 'area-detail-polygons-line', type: 'line', source: 'area-detail-polygons', paint: { 'line-color': '#92400e', 'line-width': 1.5 } })
      instance.once('render', () => emit('ready'))
      instance.on('mouseenter', 'area-detail-polygons-fill', () => setMapCursor(instance, mapDragging ? 'dragging' : 'interactive'))
      instance.on('mouseleave', 'area-detail-polygons-fill', () => setMapCursor(instance, mapDragging ? 'dragging' : 'pan'))
      instance.on('click', 'area-detail-polygons-fill', event => {
        const slug = event.features?.[0]?.properties?.slug
        if (slug) void navigateTo(`/flaechen/${slug}`)
      })
      requestAnimationFrame(() => { instance.resize(); fitArea() })
      resizeObserver = new ResizeObserver(() => instance.resize())
      resizeObserver.observe(container)
    })
    instance.on('error', (event) => {
      if (!disposed) mapError.value = event.error?.message || 'Die Kartenbasis konnte nicht vollständig geladen werden.'
    })
  } catch (error) {
    if (!disposed) mapError.value = error instanceof Error ? error.message : 'Die Karte konnte nicht geladen werden.'
  }
})

watch(() => props.area.geometry, (geometry) => {
  ;(map.value?.getSource('area-detail-boundary') as GeoJSONSource | undefined)?.setData({ type: 'Feature', properties: {}, geometry })
  fitArea()
}, { deep: true })

onBeforeUnmount(() => {
  disposed = true
  resizeObserver?.disconnect()
  map.value?.remove()
  map.value = null
})

function fitArea() {
  map.value?.fitBounds([[props.area.bbox[0], props.area.bbox[1]], [props.area.bbox[2], props.area.bbox[3]]], { padding: 42, maxZoom: 16, duration: 0 })
}
</script>
