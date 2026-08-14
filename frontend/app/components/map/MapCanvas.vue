<template>
  <div class="relative h-full min-h-0 min-w-0 overflow-hidden rounded-2xl border border-white bg-slate-100 shadow-[0_1px_12px_rgba(20,24,28,0.08)] lg:min-h-[420px]">
    <div ref="mapEl" class="absolute inset-0 h-full w-full" />
    <div v-if="!mapStore.mapLoaded && !mapError" class="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-slate-100/90" role="status" aria-live="polite">
      <div class="flex items-center gap-3 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">
        <LoaderCircle class="size-5 animate-spin text-[#154d73]" aria-hidden="true" />
        Karte wird geladen …
      </div>
    </div>
    <div class="pointer-events-none absolute right-3 top-3 z-10">
      <MapControlsContainer
        @zoom-in="map?.zoomIn()"
        @zoom-out="map?.zoomOut()"
        @reset="resetView"
      />
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
import type { FillLayerSpecification, GeoJSONSource, Map, MapLayerMouseEvent, MapMouseEvent } from 'maplibre-gl'
import { LoaderCircle, RefreshCw } from 'lucide-vue-next'
import { industryColorExpression } from '~/utils/industries'
import { osmColorExpression } from '~/utils/osmCategories'

const config = useRuntimeConfig()
const mapStore = useMapStore()
const polygonStore = usePolygonStore()
const filterStore = useFilterStore()
const osmStore = useOsmViewportStore()
const analysisAreasStore = useAnalysisAreasStore()
const mapSelection = useMapSelection()
const route = useRoute()
const mapEl = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const mapError = ref('')
const hoveredPolygonId = ref<string | null>(null)
const initialCenter: [number, number] = [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)]
const initialZoom = Number(config.public.mapZoom)
let disposed = false
let osmViewportTimer: ReturnType<typeof setTimeout> | undefined

const visibleFeatureCollection = computed<FeatureCollection>(() => ({
  type: 'FeatureCollection',
  features: polygonStore.featureCollection.features.filter(feature => (
    filterStore.activeCategories.includes(feature.properties.category as never)
    && normalizeSize(feature.properties.size) === filterStore.selectedSize
    && normalizeFloor(feature.properties.floor) === filterStore.selectedFloor
    && (!filterStore.occupancyStatuses.length || filterStore.occupancyStatuses.includes(feature.properties.occupancy_status as never))
    && (!filterStore.businessStructures.length || filterStore.businessStructures.includes(feature.properties.business_structure as never))
  ))
}))

onMounted(async () => {
  if (!mapEl.value) return
  mapStore.mapLoaded = false
  try {
    const maplibregl = await import('maplibre-gl')
    const container = mapEl.value
    if (disposed || !container?.isConnected) return
    const instance = new maplibregl.Map({
      container,
      style: String(config.public.versatilesStyleUrl),
      center: mapStore.center,
      zoom: mapStore.zoom,
      bearing: mapStore.bearing,
      pitch: mapStore.pitch,
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'low-power' }
    })
    map.value = instance
    instance.touchZoomRotate.enable()
    instance.dragRotate.enable()
    instance.on('load', async () => {
      await analysisAreasStore.load()
      ensureAnalysisAreaInfrastructure(instance)
      ensureOsmInfrastructure(instance)
      ensurePolygonInfrastructure(instance)
      mapStore.mapLoaded = true
      mapError.value = ''
      const osmRefresh = refreshOsmViewportForCurrentMap({ force: true })
      await polygonStore.loadPolygons()
      updateSource(visibleFeatureCollection.value)
      const requested = typeof route.query.polygon === 'string' ? route.query.polygon : ''
      if (requested && polygonStore.polygons.some(polygon => polygon.id === requested)) {
        await selectPolygon(requested)
      }
      await osmRefresh
    })
    instance.on('style.load', () => {
      if (!mapStore.mapLoaded || disposed) return
      ensureAnalysisAreaInfrastructure(instance)
      ensureOsmInfrastructure(instance)
      ensurePolygonInfrastructure(instance)
      updateSource(visibleFeatureCollection.value)
      void refreshOsmViewportForCurrentMap({ force: true })
    })
    instance.on('click', event => void handleMapClick(instance, event))
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
    instance.on('moveend', () => {
      mapStore.setView(
        [instance.getCenter().lng, instance.getCenter().lat], instance.getZoom(),
        instance.getBearing(), instance.getPitch()
      )
      scheduleOsmViewportRefresh()
    })
    for (const layer of ['osm-poi-hitbox', 'osm-polygons-fill']) {
      instance.on('mouseenter', layer, () => { instance.getCanvas().style.cursor = 'pointer' })
      instance.on('mouseleave', layer, () => { instance.getCanvas().style.cursor = '' })
    }
    for (const layer of ['analysis-areas-municipality-fill', 'analysis-areas-district-fill', 'analysis-areas-quarter-fill']) {
      instance.on('mouseenter', layer, () => { instance.getCanvas().style.cursor = 'pointer' })
      instance.on('mouseleave', layer, () => { instance.getCanvas().style.cursor = '' })
    }
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
  clearTimeout(osmViewportTimer)
  osmStore.dispose()
  mapStore.mapLoaded = false
  window.removeEventListener('resize', resizeMap)
  window.removeEventListener('orientationchange', resizeAfterOrientationChange)
  if (map.value) {
    mapStore.setView(
      [map.value.getCenter().lng, map.value.getCenter().lat], map.value.getZoom(),
      map.value.getBearing(), map.value.getPitch()
    )
    map.value.remove()
  }
  map.value = null
})

watch(visibleFeatureCollection, collection => updateSource(collection), { deep: true })
watch(() => polygonStore.selectedPolygonId, applyFeatureStyles)
watch(() => mapStore.categoryHighlight, applyFeatureStyles)
watch(() => mapStore.thematicStyle, applyFeatureStyles)
watch(() => osmStore.selectedFeature?.id, updateOsmSelection)
watch(() => analysisAreasStore.selectedAreaId, updateAnalysisAreaSelection)
watch(() => analysisAreasStore.visibility, setAnalysisAreaVisibility, { deep: true })
watch(() => mapStore.polygonsVisible, setPolygonVisibility)
watch(
  () => [osmStore.showPois, osmStore.showAreas, osmStore.showBuildings, osmStore.activeCategories.join(',')],
  () => scheduleOsmViewportRefresh(0)
)

function ensureOsmInfrastructure(instance: Map) {
  const empty: FeatureCollection = { type: 'FeatureCollection', features: [] }
  if (!instance.getSource('osm-pois')) {
    instance.addSource('osm-pois', {
      type: 'geojson', data: empty, cluster: true, clusterMaxZoom: 14, clusterRadius: 48
    })
  }
  if (!instance.getSource('osm-polygons')) instance.addSource('osm-polygons', { type: 'geojson', data: empty })
  if (!instance.getLayer('osm-polygons-fill')) instance.addLayer({
    id: 'osm-polygons-fill', type: 'fill', source: 'osm-polygons', minzoom: 14.5,
    paint: { 'fill-color': osmColorExpression() as ColorExpression, 'fill-opacity': 0.11 }
  })
  if (!instance.getLayer('osm-polygons-line')) instance.addLayer({
    id: 'osm-polygons-line', type: 'line', source: 'osm-polygons', minzoom: 14.5,
    paint: { 'line-color': osmColorExpression() as ColorExpression, 'line-opacity': 0.55, 'line-width': 1 }
  })
  if (!instance.getLayer('osm-clusters')) instance.addLayer({
    id: 'osm-clusters', type: 'circle', source: 'osm-pois', minzoom: 11,
    filter: ['has', 'point_count'],
    paint: { 'circle-color': '#154d73', 'circle-radius': ['step', ['get', 'point_count'], 15, 25, 19, 100, 24], 'circle-opacity': 0.82, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 }
  })
  if (!instance.getLayer('osm-cluster-count')) instance.addLayer({
    id: 'osm-cluster-count', type: 'symbol', source: 'osm-pois', minzoom: 11,
    filter: ['has', 'point_count'],
    layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 11 },
    paint: { 'text-color': '#ffffff' }
  })
  if (!instance.getLayer('osm-poi-circle')) instance.addLayer({
    id: 'osm-poi-circle', type: 'circle', source: 'osm-pois', minzoom: 12,
    filter: ['!', ['has', 'point_count']],
    paint: { 'circle-color': osmColorExpression() as ColorExpression, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 4, 17, 7], 'circle-opacity': 0.9, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 }
  })
  if (!instance.getLayer('osm-poi-hitbox')) instance.addLayer({
    id: 'osm-poi-hitbox', type: 'circle', source: 'osm-pois', minzoom: 12,
    filter: ['!', ['has', 'point_count']],
    paint: { 'circle-color': '#000000', 'circle-radius': 16, 'circle-opacity': 0.01 }
  })
  if (!instance.getLayer('osm-poi-label')) instance.addLayer({
    id: 'osm-poi-label', type: 'symbol', source: 'osm-pois', minzoom: 18,
    filter: ['all', ['!', ['has', 'point_count']], ['has', 'name']],
    layout: { 'text-field': ['get', 'name'], 'text-size': 10, 'text-offset': [0, 1.25], 'text-anchor': 'top', 'text-optional': true },
    paint: { 'text-color': '#334155', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 }
  })
  if (!instance.getLayer('osm-selected-polygon')) instance.addLayer({
    id: 'osm-selected-polygon', type: 'line', source: 'osm-polygons', minzoom: 14.5,
    filter: ['==', ['get', 'feature_id'], '__none__'],
    paint: { 'line-color': '#0f172a', 'line-width': 3 }
  })
  if (!instance.getLayer('osm-selected-point')) instance.addLayer({
    id: 'osm-selected-point', type: 'circle', source: 'osm-pois', minzoom: 11,
    filter: ['==', ['get', 'feature_id'], '__none__'],
    paint: { 'circle-color': '#ffffff', 'circle-radius': 11, 'circle-stroke-color': '#0f172a', 'circle-stroke-width': 3 }
  })
  updateOsmSelection()
}

function scheduleOsmViewportRefresh(delay = 220) {
  clearTimeout(osmViewportTimer)
  if (!map.value || disposed) return
  osmViewportTimer = setTimeout(() => void refreshOsmViewportForCurrentMap(), delay)
}

async function refreshOsmViewportForCurrentMap(options: { force?: boolean } = {}) {
  await nextTick()
  const instance = map.value
  const container = mapEl.value
  if (!instance || disposed || !container?.isConnected || container.clientWidth === 0 || container.clientHeight === 0) return
  if (!instance.isStyleLoaded() && !instance.getSource('osm-pois')) return

  instance.resize()
  if (instance.isStyleLoaded()) ensureOsmInfrastructure(instance)
  const bounds = instance.getBounds()
  const viewport = {
    west: bounds.getWest(), south: bounds.getSouth(),
    east: bounds.getEast(), north: bounds.getNorth()
  }
  const zoom = instance.getZoom()

  if (osmStore.hasCacheFor(viewport, zoom) && osmStore.data) updateOsmSources(osmStore.data)
  const data = await osmStore.load(viewport, zoom, options)
  if (!disposed && map.value === instance && data) updateOsmSources(data)
}

function updateOsmSources(data = osmStore.data) {
  if (!map.value || !data) return
  const started = performance.now()
  const generation = osmStore.generation
  const pointFeatures = data.features.filter(feature => feature.properties.feature_type === 'point')
  const polygonFeatures = data.features.filter(feature => feature.properties.feature_type === 'polygon')
  const points: FeatureCollection = { type: 'FeatureCollection', features: pointFeatures } as FeatureCollection
  const polygons: FeatureCollection = { type: 'FeatureCollection', features: polygonFeatures } as FeatureCollection
  ;(map.value.getSource('osm-pois') as GeoJSONSource | undefined)?.setData(points)
  ;(map.value.getSource('osm-polygons') as GeoJSONSource | undefined)?.setData(polygons)
  map.value.once('idle', () => {
    if (generation === osmStore.generation) osmStore.setRenderDuration(performance.now() - started)
  })
}

function updateOsmSelection() {
  const selected = osmStore.selectedFeature?.id || '__none__'
  for (const layer of ['osm-selected-point', 'osm-selected-polygon']) {
    if (map.value?.getLayer(layer)) map.value.setFilter(layer, ['==', ['get', 'feature_id'], selected])
  }
}

async function handleMapClick(instance: Map, event: MapMouseEvent) {
  const hits = instance.queryRenderedFeatures(event.point, {
    layers: ['overview-polygons-fill', 'osm-clusters', 'osm-poi-hitbox', 'osm-polygons-fill']
  })
  const cityPolygon = hits.find(feature => feature.layer.id === 'overview-polygons-fill')
  if (cityPolygon?.properties?.id) {
    await selectPolygon(String(cityPolygon.properties.id))
    return
  }
  const cluster = hits.find(feature => feature.layer.id === 'osm-clusters')
  if (cluster?.properties?.cluster_id != null) {
    const source = instance.getSource('osm-pois') as GeoJSONSource
    const zoom = await source.getClusterExpansionZoom(Number(cluster.properties.cluster_id))
    const coordinates = cluster.geometry.type === 'Point' ? cluster.geometry.coordinates : null
    if (coordinates?.[0] != null && coordinates[1] != null) {
      instance.easeTo({ center: [coordinates[0], coordinates[1]], zoom })
    }
    return
  }
  const osmHit = hits.find(feature => ['osm-poi-hitbox', 'osm-polygons-fill'].includes(feature.layer.id))
  const featureId = osmHit?.properties?.feature_id
  const feature = osmStore.data?.features.find(item => item.id === featureId)
  if (feature) {
    const detailRequest = mapSelection.selectOsm(feature)
    if (window.matchMedia('(max-width: 1023px)').matches) mapStore.openMobilePanel('analytics')
    await detailRequest
    return
  }
  const areaHits = instance.queryRenderedFeatures(event.point, {
    layers: ['analysis-areas-quarter-fill', 'analysis-areas-district-fill', 'analysis-areas-municipality-fill']
  })
  const areaHit = ['analysis-areas-quarter-fill', 'analysis-areas-district-fill', 'analysis-areas-municipality-fill']
    .map(layer => areaHits.find(item => item.layer.id === layer)).find(Boolean)
  if (areaHit?.properties?.id) {
    const detailRequest = mapSelection.selectAnalysisArea(String(areaHit.properties.id))
    if (window.matchMedia('(max-width: 1023px)').matches) mapStore.openMobilePanel('analytics')
    await detailRequest
  } else {
    mapSelection.clearSelection()
    mapStore.closeMobilePanels()
  }
}

function ensureAnalysisAreaInfrastructure(instance: Map) {
  if (!instance.getSource('analysis-areas')) instance.addSource('analysis-areas', { type: 'geojson', data: analysisAreasStore.featureCollection })
  const layers = [
    { id: 'analysis-areas-municipality', type: 'MUNICIPALITY', minzoom: 7, color: '#2563eb', opacity: 0.035, width: 2.2 },
    { id: 'analysis-areas-district', type: 'DISTRICT', minzoom: 9.5, color: '#15803d', opacity: 0.045, width: 1.5 },
    { id: 'analysis-areas-quarter', type: 'QUARTER', minzoom: 11.5, color: '#b45309', opacity: 0.045, width: 1 }
  ] as const
  for (const layer of layers) {
    if (!instance.getLayer(`${layer.id}-fill`)) instance.addLayer({
      id: `${layer.id}-fill`, type: 'fill', source: 'analysis-areas', minzoom: layer.minzoom,
      filter: ['==', ['get', 'area_type'], layer.type], paint: { 'fill-color': layer.color, 'fill-opacity': layer.opacity }
    })
    if (!instance.getLayer(layer.id)) instance.addLayer({
      id: layer.id, type: 'line', source: 'analysis-areas', minzoom: layer.minzoom,
      filter: ['==', ['get', 'area_type'], layer.type], paint: { 'line-color': layer.color, 'line-opacity': 0.72, 'line-width': layer.width }
    })
    if (!instance.getLayer(`${layer.id}-label`)) instance.addLayer({
      id: `${layer.id}-label`, type: 'symbol', source: 'analysis-areas', minzoom: layer.minzoom + 0.8,
      filter: ['==', ['get', 'area_type'], layer.type],
      layout: { 'text-field': ['get', 'name'], 'text-size': layer.type === 'MUNICIPALITY' ? 13 : 11, 'text-optional': true },
      paint: { 'text-color': layer.color, 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 }
    })
  }
  if (!instance.getLayer('analysis-area-selected')) instance.addLayer({
    id: 'analysis-area-selected', type: 'line', source: 'analysis-areas',
    filter: ['==', ['get', 'id'], '__none__'],
    paint: { 'line-color': '#0f172a', 'line-width': 3.5, 'line-opacity': 0.95 }
  })
  setAnalysisAreaVisibility()
  updateAnalysisAreaSelection()
}

function setAnalysisAreaVisibility() {
  if (!map.value) return
  for (const [type, suffix] of [['MUNICIPALITY', 'municipality'], ['DISTRICT', 'district'], ['QUARTER', 'quarter']] as const) {
    const visibility = analysisAreasStore.visibility[type] ? 'visible' : 'none'
    for (const ending of ['-fill', '', '-label']) {
      const layer = `analysis-areas-${suffix}${ending}`
      if (map.value.getLayer(layer)) map.value.setLayoutProperty(layer, 'visibility', visibility)
    }
  }
}

function updateAnalysisAreaSelection() {
  if (map.value?.getLayer('analysis-area-selected')) {
    map.value.setFilter('analysis-area-selected', ['==', ['get', 'id'], analysisAreasStore.selectedAreaId || '__none__'])
  }
}

function ensurePolygonInfrastructure(instance: Map) {
  if (!instance.getSource('overview-polygons')) instance.addSource('overview-polygons', { type: 'geojson', data: visibleFeatureCollection.value })
  if (!instance.getLayer('overview-polygons-fill')) instance.addLayer({
    id: 'overview-polygons-fill',
    type: 'fill',
    source: 'overview-polygons',
    paint: { 'fill-color': thematicColorExpression(), 'fill-opacity': 0.3 }
  })
  if (!instance.getLayer('overview-polygons-line')) instance.addLayer({
    id: 'overview-polygons-line',
    type: 'line',
    source: 'overview-polygons',
    paint: { 'line-color': categoryColorExpression(), 'line-width': 2 }
  })
  applyFeatureStyles()
  setPolygonVisibility(mapStore.polygonsVisible)
}

async function selectPolygon(id: string) {
  await mapSelection.selectPolygon(id)
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
  map.value.setPaintProperty('overview-polygons-fill', 'fill-color', thematicColorExpression())
  map.value.setPaintProperty('overview-polygons-line', 'line-color', [
    'case', ['==', ['get', 'id'], selected], '#0f172a', categoryColorExpression()
  ])
  map.value.setPaintProperty('overview-polygons-line', 'line-width', [
    'case', ['==', ['get', 'id'], selected], 3.5, ['==', ['get', 'id'], hovered], 3, 2
  ])
}

type ColorExpression = NonNullable<NonNullable<FillLayerSpecification['paint']>['fill-color']>

function categoryColorExpression() { return industryColorExpression() as ColorExpression }

function thematicColorExpression() {
  if (mapStore.thematicStyle === 'occupancy') {
    return ['match', ['get', 'occupancy_status'], 'OCCUPIED', '#10b981', 'VACANT', '#f43f5e', '#94a3b8'] as ColorExpression
  }
  if (mapStore.thematicStyle === 'size') {
    return ['match', ['get', 'size'], 'S', '#dbeafe', 'M', '#93c5fd', 'L', '#3b82f6', 'XL', '#1e3a8a', '#94a3b8'] as ColorExpression
  }
  if (mapStore.thematicStyle === 'business') {
    return ['match', ['get', 'business_structure'], 'CHAIN', '#7c3aed', 'INDEPENDENT', '#f59e0b', '#94a3b8'] as ColorExpression
  }
  return categoryColorExpression()
}

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
