<template>
  <section class="overflow-hidden rounded-xl border border-[#dfe4e6] bg-white" aria-labelledby="polygon-map-heading">
    <div class="flex flex-col items-stretch justify-between gap-3 border-b border-[#dfe4e6] px-4 py-4 sm:flex-row sm:items-center sm:px-5">
      <h2 id="polygon-map-heading" class="text-lg font-bold text-[#202427]">Karte</h2>
      <div class="grid grid-cols-1 gap-2 min-[390px]:grid-cols-2 sm:flex sm:flex-wrap sm:justify-end">
        <button type="button" class="min-h-11 rounded-xl border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50" @click="fitPolygon">
          Polygon zentrieren
        </button>
        <button
          v-if="editable"
          type="button"
          class="min-h-11 rounded-xl bg-[#154d73] px-4 text-sm font-bold text-white"
          @click="editing ? finishEditing() : startEditing()"
        >
          {{ editing ? 'Bearbeitung abschließen' : 'Polygon bearbeiten' }}
        </button>
      </div>
    </div>
    <div class="relative">
      <div ref="mapElement" class="h-[clamp(320px,46dvh,480px)] w-full sm:h-[480px] lg:h-[520px]" />
      <p v-if="mapError" class="absolute inset-x-4 top-4 z-10 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-rose-700 shadow" role="alert">
        {{ mapError }}
      </p>
    </div>
    <p v-if="editing" class="border-t border-[#dfe4e6] px-4 py-3 text-sm leading-6 text-[#687176] sm:px-5">
      Punkte per Touch oder Maus verschieben und anschließend „Bearbeitung abschließen“ wählen. Währenddessen ist das Verschieben der Karte gesperrt. Erst dann wird gespeichert.
    </p>
  </section>
</template>

<script setup lang="ts">
import type { GeoJSONSource, Map } from 'maplibre-gl'
import type { TerraDraw } from 'terra-draw'
import type { AreaGeometry, PolygonGeometry } from '~/types/geo'
import { loadMapStyle } from '~/config/mapStyles'

const props = defineProps<{
  geometry: AreaGeometry
  bbox: [number, number, number, number]
  editable: boolean
  color: string
}>()
const emit = defineEmits<{ geometryComplete: [geometry: AreaGeometry] }>()

const config = useRuntimeConfig()
const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const draw = shallowRef<TerraDraw | null>(null)
const editing = ref(false)
const draftGeometry = shallowRef<AreaGeometry | null>(null)
const editorFeatureIds = shallowRef<Array<string | number>>([])
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
      bounds: [[props.bbox[0], props.bbox[1]], [props.bbox[2], props.bbox[3]]],
      fitBoundsOptions: { padding: 52, maxZoom: 18 },
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'low-power' }
    })
    map.value = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    instance.on('load', () => {
      instance.addSource('detail-polygon', { type: 'geojson', data: featureCollection(props.geometry) })
      instance.addLayer({
        id: 'detail-polygon-fill',
        type: 'fill',
        source: 'detail-polygon',
        paint: { 'fill-color': props.color, 'fill-opacity': 0.25 }
      })
      instance.addLayer({
        id: 'detail-polygon-line',
        type: 'line',
        source: 'detail-polygon',
        paint: { 'line-color': props.color, 'line-width': 3 }
      })
      requestAnimationFrame(() => {
        instance.resize()
        fitPolygon()
      })

      const terra = new terraDraw.TerraDraw({
        adapter: new adapter.TerraDrawMapLibreGLAdapter({ map: instance }),
        modes: [
          new terraDraw.TerraDrawPolygonMode(),
          new terraDraw.TerraDrawSelectMode({
            styles: {
              selectedPolygonColor: () => props.color as `#${string}`,
              selectedPolygonFillOpacity: 0.25,
              selectedPolygonOutlineColor: () => props.color as `#${string}`,
              selectedPolygonOutlineWidth: 4,
              selectionPointColor: '#ffffff',
              selectionPointOutlineColor: () => props.color as `#${string}`,
              midPointColor: () => props.color as `#${string}`
            },
            flags: {
              polygon: {
                feature: { draggable: true, rotateable: false, scaleable: false, coordinates: { midpoints: true, draggable: true, deletable: true } }
              }
            }
          })
        ]
      })
      terra.on('change', (ids: Array<string | number>, type: string) => {
        if (!editing.value || type !== 'update' || !ids.some(id => editorFeatureIds.value.includes(id))) return
        const polygons = editorFeatureIds.value
          .map(id => terra.getSnapshotFeature(id)?.geometry)
          .filter((geometry): geometry is PolygonGeometry => geometry?.type === 'Polygon')
        if (!polygons.length) return
        draftGeometry.value = polygons.length === 1
          ? polygons[0]!
          : { type: 'MultiPolygon', coordinates: polygons.map(item => item.coordinates) }
      })
      terra.start()
      draw.value = terra

      resizeObserver = new ResizeObserver(() => instance.resize())
      resizeObserver.observe(container)
    })
    instance.on('error', (event) => {
      if (disposed) return
      console.warn('Detail map resource error', event.error)
      mapError.value = 'Die Kartenbasis konnte nicht vollständig geladen werden.'
    })
    instance.on('webglcontextlost', () => {
      if (!disposed) mapError.value = 'Die Kartenanzeige wird nach einem Grafikfehler wiederhergestellt.'
    })
    instance.on('webglcontextrestored', () => {
      if (!disposed) mapError.value = ''
    })
  } catch (error) {
    if (disposed) return
    mapError.value = error instanceof Error ? error.message : 'Die Karte konnte nicht geladen werden.'
  }
})

watch(() => props.geometry, (geometry) => {
  if (editing.value) return
  const source = map.value?.getSource('detail-polygon') as GeoJSONSource | undefined
  source?.setData(featureCollection(geometry))
}, { deep: true })

watch(() => props.color, (color) => {
  const instance = map.value
  if (!instance?.getLayer('detail-polygon-fill')) return
  instance.setPaintProperty('detail-polygon-fill', 'fill-color', color)
  instance.setPaintProperty('detail-polygon-line', 'line-color', color)
})

onBeforeUnmount(() => {
  disposed = true
  resizeObserver?.disconnect()
  resizeObserver = null
  draw.value?.stop()
  map.value?.remove()
  draw.value = null
  map.value = null
})

function fitPolygon() {
  map.value?.fitBounds(
    [[props.bbox[0], props.bbox[1]], [props.bbox[2], props.bbox[3]]],
    { padding: 52, maxZoom: 18, duration: 0 }
  )
}

function startEditing() {
  const terra = draw.value
  if (!terra || !props.editable) return
  draftGeometry.value = props.geometry
  if (!editorFeatureIds.value.length) {
    const polygons = props.geometry.type === 'Polygon'
      ? [props.geometry]
      : props.geometry.coordinates.map(coordinates => ({ type: 'Polygon' as const, coordinates }))
    const validations = terra.addFeatures(polygons.map(geometry => ({
      type: 'Feature' as const,
      id: terra.getFeatureId(),
      geometry,
      properties: { mode: 'polygon' }
    })))
    const featureIds = validations
      .filter(validation => validation.valid && validation.id != null && terra.hasFeature(validation.id))
      .map(validation => validation.id as string | number)
    if (featureIds.length !== polygons.length) {
      if (featureIds.length) terra.removeFeatures(featureIds)
      draftGeometry.value = null
      editorFeatureIds.value = []
      return
    }
    editorFeatureIds.value = featureIds
  }
  editing.value = true
  map.value?.dragPan.disable()
  map.value?.touchZoomRotate.disable()
  setStaticPolygonVisibility(false)
  if (editorFeatureIds.value[0] != null) terra.selectFeature(editorFeatureIds.value[0])
}

function finishEditing() {
  if (!editing.value) return
  editing.value = false
  map.value?.dragPan.enable()
  map.value?.touchZoomRotate.enable()
  const geometry = draftGeometry.value
  const terra = draw.value
  const featureIds = editorFeatureIds.value
  if (terra && featureIds.length) terra.removeFeatures(featureIds.filter(id => terra.hasFeature(id)))
  editorFeatureIds.value = []
  draftGeometry.value = null
  setStaticPolygonVisibility(true)
  if (geometry && JSON.stringify(geometry.coordinates) !== JSON.stringify(props.geometry.coordinates)) {
    emit('geometryComplete', geometry)
  }
}

function setStaticPolygonVisibility(visible: boolean) {
  const instance = map.value
  if (!instance?.getLayer('detail-polygon-fill')) return
  const visibility = visible ? 'visible' : 'none'
  instance.setLayoutProperty('detail-polygon-fill', 'visibility', visibility)
  instance.setLayoutProperty('detail-polygon-line', 'visibility', visibility)
}

function featureCollection(geometry: AreaGeometry) {
  return {
    type: 'FeatureCollection' as const,
    features: [{ type: 'Feature' as const, geometry, properties: {} }]
  }
}
</script>
