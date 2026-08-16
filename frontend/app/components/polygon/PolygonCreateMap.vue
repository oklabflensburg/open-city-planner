<template>
  <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-labelledby="create-map-heading">
    <div class="flex flex-col items-stretch justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:flex-row sm:items-center sm:px-5">
      <div class="min-w-0">
        <h2 id="create-map-heading" class="font-bold text-slate-950">Fläche zeichnen</h2>
        <p class="mt-1 text-sm text-slate-600">Setzen Sie mindestens drei Eckpunkte und schließen Sie das Polygon am ersten Punkt.</p>
      </div>
      <button v-if="geometry" class="min-h-11 shrink-0 rounded-xl border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50" type="button" @click="resetDrawing">Neu zeichnen</button>
    </div>
    <div class="relative">
      <div ref="mapElement" class="h-[clamp(320px,50dvh,520px)] w-full sm:h-[560px]" />
      <p v-if="mapError" class="absolute inset-x-4 top-4 z-10 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-rose-700 shadow" role="alert">{{ mapError }}</p>
      <div class="pointer-events-none absolute bottom-12 left-1/2 z-10 w-max max-w-[calc(100%-1.5rem)] -translate-x-1/2 rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-center text-xs font-semibold leading-5 text-slate-700 shadow-lg backdrop-blur sm:bottom-4 sm:px-4">
        {{ geometry ? 'Polygon ist bereit. Sie können es neu zeichnen oder die Fläche erstellen.' : 'Klicken oder tippen Sie, um Eckpunkte zu setzen.' }}
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { Map } from 'maplibre-gl'
import type { TerraDraw } from 'terra-draw'
import type { PolygonGeometry } from '~/types/geo'
import { loadMapStyle } from '~/config/mapStyles'

const props = defineProps<{ color: string, center?: [number, number] }>()
const emit = defineEmits<{ 'update:geometry': [geometry: PolygonGeometry | null] }>()
const config = useRuntimeConfig()
const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const draw = shallowRef<TerraDraw | null>(null)
const geometry = shallowRef<PolygonGeometry | null>(null)
const completedFeatureId = shallowRef<string | number | null>(null)
const mapError = ref('')
let resizeObserver: ResizeObserver | null = null
let disposed = false

onMounted(async () => {
  const container = mapElement.value
  if (!container) return
  try {
    const [{ default: maplibregl }, terraDraw, adapter, mapStyle] = await Promise.all([
      import('maplibre-gl'),
      import('terra-draw'),
      import('terra-draw-maplibre-gl-adapter'),
      loadMapStyle(String(config.public.mapStyleUrl || '')),
      import('maplibre-gl/dist/maplibre-gl.css')
    ])
    if (disposed || !container.isConnected) return
    const instance = new maplibregl.Map({
      container,
      style: mapStyle,
      center: props.center || [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)],
      zoom: props.center ? 19 : Number(config.public.mapZoom),
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'low-power' }
    })
    map.value = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    instance.on('load', () => {
      const terra = new terraDraw.TerraDraw({
        adapter: new adapter.TerraDrawMapLibreGLAdapter({ map: instance }),
        modes: [new terraDraw.TerraDrawPolygonMode({
          styles: {
            fillColor: () => props.color as `#${string}`,
            fillOpacity: 0.25,
            outlineColor: () => props.color as `#${string}`,
            outlineWidth: 3
          }
        })]
      })
      terra.on('finish', (id: string | number) => {
        const feature = terra.getSnapshotFeature(id)
        if (feature?.geometry.type !== 'Polygon') return
        const previous = completedFeatureId.value
        if (previous != null && previous !== id && terra.hasFeature(previous)) terra.removeFeatures([previous])
        completedFeatureId.value = id
        geometry.value = feature.geometry as PolygonGeometry
        emit('update:geometry', geometry.value)
      })
      terra.start()
      terra.setMode('polygon')
      draw.value = terra
      resizeObserver = new ResizeObserver(() => instance.resize())
      resizeObserver.observe(container)
      requestAnimationFrame(() => instance.resize())
    })
    instance.on('error', () => {
      if (!disposed) mapError.value = 'Die Kartenbasis konnte nicht vollständig geladen werden.'
    })
  } catch (error) {
    if (!disposed) mapError.value = error instanceof Error ? error.message : 'Die Karte konnte nicht geladen werden.'
  }
})

onBeforeUnmount(() => {
  disposed = true
  resizeObserver?.disconnect()
  draw.value?.stop()
  map.value?.remove()
  draw.value = null
  map.value = null
})

function resetDrawing() {
  const terra = draw.value
  if (terra) {
    const ids = terra.getSnapshot().map(feature => feature.id).filter((id): id is string | number => id != null)
    if (ids.length) terra.removeFeatures(ids)
    terra.setMode('polygon')
  }
  completedFeatureId.value = null
  geometry.value = null
  emit('update:geometry', null)
}
</script>
