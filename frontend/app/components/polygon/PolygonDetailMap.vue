<template>
  <section class="overflow-hidden rounded-xl border border-[#dfe4e6] bg-white" aria-labelledby="polygon-map-heading">
    <div class="flex items-center justify-between gap-4 border-b border-[#dfe4e6] px-5 py-4">
      <h2 id="polygon-map-heading" class="text-lg font-bold text-[#202427]">Karte</h2>
      <button
        v-if="editable"
        type="button"
        class="min-h-10 rounded-md bg-[#154d73] px-4 text-sm font-bold text-white"
        @click="editing ? finishEditing() : startEditing()"
      >
        {{ editing ? 'Bearbeitung abschließen' : 'Polygon bearbeiten' }}
      </button>
    </div>
    <div ref="mapElement" class="h-[420px] w-full" />
    <p v-if="editing" class="border-t border-[#dfe4e6] px-5 py-3 text-sm text-[#687176]">
      Punkte verschieben und anschließend „Bearbeitung abschließen“ wählen. Erst dann wird gespeichert.
    </p>
  </section>
</template>

<script setup lang="ts">
import type { GeoJSONSource, Map } from 'maplibre-gl'
import type { TerraDraw } from 'terra-draw'
import type { PolygonGeometry } from '~/types/geo'

const props = defineProps<{
  geometry: PolygonGeometry
  bbox: [number, number, number, number]
  editable: boolean
}>()
const emit = defineEmits<{ geometryComplete: [geometry: PolygonGeometry] }>()

const config = useRuntimeConfig()
const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const draw = shallowRef<TerraDraw | null>(null)
const editing = ref(false)
const draftGeometry = shallowRef<PolygonGeometry | null>(null)
const featureId = 'detail-polygon-editor'

onMounted(async () => {
  if (!mapElement.value) return
  const [{ default: maplibregl }, terraDraw, adapter] = await Promise.all([
    import('maplibre-gl'),
    import('terra-draw'),
    import('terra-draw-maplibre-gl-adapter')
  ])
  const instance = new maplibregl.Map({
    container: mapElement.value,
    style: String(config.public.versatilesStyleUrl),
    bounds: [[props.bbox[0], props.bbox[1]], [props.bbox[2], props.bbox[3]]],
    fitBoundsOptions: { padding: 52, maxZoom: 18 },
    attributionControl: { compact: true }
  })
  map.value = instance
  instance.on('load', () => {
    instance.addSource('detail-polygon', { type: 'geojson', data: featureCollection(props.geometry) })
    instance.addLayer({
      id: 'detail-polygon-fill',
      type: 'fill',
      source: 'detail-polygon',
      paint: { 'fill-color': '#154d73', 'fill-opacity': 0.25 }
    })
    instance.addLayer({
      id: 'detail-polygon-line',
      type: 'line',
      source: 'detail-polygon',
      paint: { 'line-color': '#154d73', 'line-width': 3 }
    })

    const terra = new terraDraw.TerraDraw({
      adapter: new adapter.TerraDrawMapLibreGLAdapter({ map: instance }),
      modes: [new terraDraw.TerraDrawSelectMode({
        flags: {
          polygon: {
            feature: { draggable: true, rotateable: false, scaleable: false, coordinates: { midpoints: true, draggable: true, deletable: true } }
          }
        }
      })]
    })
    terra.on('change', (ids: Array<string | number>, type: string) => {
      if (!editing.value || type !== 'update' || !ids.some(id => String(id) === featureId)) return
      const feature = terra.getSnapshotFeature(featureId)
      if (feature?.geometry.type === 'Polygon') draftGeometry.value = feature.geometry as PolygonGeometry
    })
    terra.on('deselect', (id: string | number) => {
      if (editing.value && String(id) === featureId) finishEditing()
    })
    terra.start()
    draw.value = terra
  })
})

watch(() => props.geometry, (geometry) => {
  if (editing.value) return
  const source = map.value?.getSource('detail-polygon') as GeoJSONSource | undefined
  source?.setData(featureCollection(geometry))
}, { deep: true })

onBeforeUnmount(() => {
  draw.value?.stop()
  map.value?.remove()
})

function startEditing() {
  const terra = draw.value
  if (!terra || !props.editable) return
  draftGeometry.value = props.geometry
  if (!terra.hasFeature(featureId)) {
    terra.addFeatures([{
      type: 'Feature',
      id: featureId,
      geometry: props.geometry,
      properties: { mode: 'polygon' }
    }])
  }
  editing.value = true
  terra.selectFeature(featureId)
}

function finishEditing() {
  if (!editing.value) return
  editing.value = false
  const geometry = draftGeometry.value
  const terra = draw.value
  if (terra?.hasFeature(featureId)) terra.removeFeatures([featureId])
  draftGeometry.value = null
  if (geometry && JSON.stringify(geometry.coordinates) !== JSON.stringify(props.geometry.coordinates)) {
    emit('geometryComplete', geometry)
  }
}

function featureCollection(geometry: PolygonGeometry) {
  return {
    type: 'FeatureCollection' as const,
    features: [{ type: 'Feature' as const, geometry, properties: {} }]
  }
}
</script>
