<template>
  <div class="relative h-full min-h-0 min-w-0 overflow-hidden rounded-[var(--radius-panel)] border border-white bg-[var(--c-surface-muted)] shadow-[var(--shadow-card)] lg:min-h-[420px]">
    <span v-if="socialPreview" class="sr-only" :data-social-preview-ready="gisPreviewReady ? 'true' : 'false'">Kartenvorschau bereit</span>
    <div ref="mapEl" class="absolute inset-0 h-full w-full" role="region" aria-label="Interaktive Stadtkarte von Flensburg" />
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
      <button class="mt-3 inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl bg-[#154d73] px-4 text-sm font-bold text-white hover:bg-[#0f3f61]" type="button" @click="retryMap">
        <RefreshCw class="size-4" aria-hidden="true" /> Erneut versuchen
      </button>
    </div>
    <div v-else-if="polygonStore.error" class="absolute bottom-24 left-3 z-10 max-w-[calc(100%-1.5rem)] rounded-lg bg-white px-3 py-2 text-xs text-red-700 shadow lg:bottom-16 lg:max-w-[320px]">
      {{ polygonStore.error }}
    </div>
    <div v-else-if="showEmptyState" class="absolute bottom-3 left-3 z-10 flex max-w-[calc(100%-1.5rem)] items-center gap-3 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow lg:bottom-4 lg:max-w-[360px]" role="status" aria-live="polite">
      <span class="font-semibold">0 Treffer für die aktuelle Auswahl</span>
      <button class="min-h-8 shrink-0 cursor-pointer rounded-md px-2 font-bold text-[#154d73] hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" @click="filterStore.reset()">Filter aufheben</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FeatureCollection } from 'geojson'
import type { FillLayerSpecification, GeoJSONSource, Map, MapMouseEvent } from 'maplibre-gl'
import { LoaderCircle, RefreshCw } from 'lucide-vue-next'
import type { OsmViewportResult } from '~/types/osm'
import { getIndustryColor, industryColorExpression } from '~/utils/industries'
import { thematicColor, thematicColorExpression } from '~/utils/mapThemes'
import { osmCategoryColors, osmColorExpression } from '~/utils/osmCategories'
import { shouldExcludeOsmFeature } from '~/utils/osmExclusions'
import { pickMapEntityAtPoint, type InteractivePolygonFeature } from '~/utils/mapFeaturePicking'
import { ensureStadtplanerLayerOrder, getStadtplanerLayerOrder, hasValidStadtplanerLayerOrder } from '~/utils/mapLayerOrder'
import { setMapCursor } from '~/utils/mapCursor'
import { loadMapStyle } from '~/config/mapStyles'

const config = useRuntimeConfig()
const mapStore = useMapStore()
const polygonStore = usePolygonStore()
const filterStore = useFilterStore()
const osmStore = useOsmViewportStore()
const analysisAreasStore = useAnalysisAreasStore()
const mapSelection = useMapSelection()
const route = useRoute()
const socialPreview = computed(() => route.query['social-preview'] === '1')
const gisPreviewReady = ref(false)
const mapEl = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const mapError = ref('')
const initialCenter: [number, number] = [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)]
const initialZoom = Number(config.public.mapZoom)
let disposed = false
let osmViewportTimer: ReturnType<typeof setTimeout> | undefined
let forceNextOsmRefresh = false
let hoverFrame: number | undefined
let mapDragging = false
let pendingHoverPoint: { x: number, y: number } | null = null
let hoveredPolygonId: string | null = null
let selectedOsmState: { source: 'osm-pois', id: string } | null = null
const performanceCounters = {
  viewportFetches: 0,
  osmSetDataCalls: 0,
  polygonSetDataCalls: 0,
  osmFeatures: 0,
  osmVertices: 0,
  osmPayloadBytes: 0,
  lastOsmRenderMs: 0
}
const performanceDebugEnabled = import.meta.dev || config.public.mapPerformanceDebug

const visibleFeatureCollection = computed<FeatureCollection>(() => polygonStore.featureCollection as FeatureCollection)
const showEmptyState = computed(() => filterStore.activeFilterCount > 0 && filterStore.selectedSources.length > 0
  && !polygonStore.loading && !osmStore.loading
  && polygonStore.polygons.length === 0 && (osmStore.data?.meta.business_count || 0) === 0)

onMounted(async () => {
  if (!mapEl.value) return
  mapStore.mapLoaded = false
  try {
    const [maplibregl, mapStyle] = await Promise.all([
      import('maplibre-gl'),
      loadMapStyle(String(config.public.mapStyleUrl || '')),
      import('maplibre-gl/dist/maplibre-gl.css')
    ])
    const container = mapEl.value
    if (disposed || !container?.isConnected) return
    const instance = new maplibregl.Map({
      container,
      style: mapStyle,
      center: mapStore.center,
      zoom: mapStore.zoom,
      bearing: mapStore.bearing,
      pitch: mapStore.pitch,
      attributionControl: { compact: true },
      canvasContextAttributes: { powerPreference: 'high-performance' }
    })
    map.value = markRaw(instance)
    setMapCursor(instance, 'pan')
    installPerformanceDebug(instance)
    instance.touchZoomRotate.enable()
    instance.dragRotate.enable()
    instance.on('load', async () => {
      await analysisAreasStore.load()
      ensureMapInfrastructure(instance)
      mapStore.mapLoaded = true
      mapError.value = ''
      const osmRefresh = refreshOsmViewportForCurrentMap({ force: true })
      await polygonStore.loadPolygons()
      updateSource(visibleFeatureCollection.value)
      const requested = typeof route.query.polygon === 'string' ? route.query.polygon : ''
      if (requested && polygonStore.polygons.some(polygon => polygon.id === requested)) {
        await selectPolygon(requested, true)
      } else {
        await selectRequestedArea(instance)
      }
      await osmRefresh
      mapStore.markGisDataFresh()
      if (socialPreview.value && requested && polygonStore.selectedPolygonId === requested) {
        await waitForGisPreviewReady(instance)
        gisPreviewReady.value = true
      }
    })
    instance.on('style.load', () => {
      if (!mapStore.mapLoaded || disposed) return
      ensureMapInfrastructure(instance)
      updateSource(visibleFeatureCollection.value)
      void refreshOsmViewportForCurrentMap({ force: true })
    })
    instance.on('click', event => void handleMapClick(instance, event))
    instance.on('mousemove', event => handleMapHover(instance, event))
    instance.on('dragstart', () => {
      mapDragging = true
      setMapCursor(instance, 'dragging')
    })
    instance.on('dragend', () => {
      mapDragging = false
      setMapCursor(instance, 'pan')
    })
    instance.getCanvas().addEventListener('mouseleave', () => {
      setMapCursor(instance, mapDragging ? 'dragging' : 'pan')
      updatePolygonHover(null)
    })
    instance.on('moveend', () => {
      mapStore.setView(
        [instance.getCenter().lng, instance.getCenter().lat], instance.getZoom(),
        instance.getBearing(), instance.getPitch()
      )
      scheduleOsmViewportRefresh()
    })
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
  clearTimeout(polygonFilterTimer)
  if (hoverFrame !== undefined) cancelAnimationFrame(hoverFrame)
  osmStore.dispose()
  mapStore.mapLoaded = false
  window.removeEventListener('resize', resizeMap)
  window.removeEventListener('orientationchange', resizeAfterOrientationChange)
  if (map.value) {
    mapStore.setView(
      [map.value.getCenter().lng, map.value.getCenter().lat], map.value.getZoom(),
      map.value.getBearing(), map.value.getPitch()
    )
    clearSelectionRendering()
    map.value.remove()
  }
  map.value = null
  if (import.meta.client) delete window.__stadtplanerMapPerformance
})

watch(visibleFeatureCollection, (collection) => {
  updateSource(collection)
  if (polygonStore.selectedPolygonId && !polygonStore.polygons.some(item => item.id === polygonStore.selectedPolygonId)) {
    mapSelection.clearSelection()
  }
}, { deep: true })
let polygonFilterTimer: ReturnType<typeof setTimeout> | undefined
watch(() => filterStore.filterKey, () => {
  clearTimeout(polygonFilterTimer)
  polygonFilterTimer = setTimeout(() => void polygonStore.loadPolygons(), 200)
  scheduleOsmViewportRefresh(200)
})
watch(() => mapStore.selectedMapEntity, () => {
  updateSelectedPolygonOverlay()
  updateOsmSelection()
})
watch(() => mapStore.categoryHighlight, applyFeatureStyles)
watch(() => mapStore.thematicStyle, () => {
  applyFeatureStyles()
  updateSelectedPolygonOverlay()
})
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
      type: 'geojson', data: empty, promoteId: 'feature_id', cluster: true, clusterMaxZoom: 14, clusterRadius: 48
    })
  }
  if (!instance.getSource('osm-polygons')) instance.addSource('osm-polygons', { type: 'geojson', data: empty, promoteId: 'feature_id' })
  if (!instance.getLayer('osm-polygons-fill')) instance.addLayer({
    id: 'osm-polygons-fill', type: 'fill', source: 'osm-polygons', minzoom: 14.5,
    filter: ['!=', ['get', 'natural'], 'peninsula'],
    paint: { 'fill-color': osmBusinessColorExpression(), 'fill-opacity': 0.11 }
  })
  if (!instance.getLayer('osm-polygons-line')) instance.addLayer({
    id: 'osm-polygons-line', type: 'line', source: 'osm-polygons', minzoom: 14.5,
    filter: ['!=', ['get', 'natural'], 'peninsula'],
    paint: { 'line-color': osmBusinessColorExpression(), 'line-opacity': 0.65, 'line-width': 1 }
  })
  if (!instance.getLayer('osm-clusters')) instance.addLayer({
    id: 'osm-clusters', type: 'circle', source: 'osm-pois', minzoom: 11,
    filter: ['has', 'point_count'],
    paint: { 'circle-color': '#154d73', 'circle-radius': ['step', ['get', 'point_count'], 15, 25, 19, 100, 24], 'circle-opacity': 0.82, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 }
  })
  if (!instance.getLayer('osm-cluster-count')) instance.addLayer({
    id: 'osm-cluster-count', type: 'symbol', source: 'osm-pois', minzoom: 11,
    filter: ['has', 'point_count'],
    layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['noto_sans_regular'], 'text-size': 11 },
    paint: { 'text-color': '#ffffff' }
  })
  if (!instance.getLayer('osm-poi-circle')) instance.addLayer({
    id: 'osm-poi-circle', type: 'circle', source: 'osm-pois', minzoom: 12,
    filter: ['all', ['!', ['has', 'point_count']], ['!=', ['get', 'natural'], 'peninsula']],
    paint: { 'circle-color': osmBusinessColorExpression(), 'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 4, 17, 7], 'circle-opacity': 0.9, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 }
  })
  if (!instance.getLayer('osm-poi-label')) instance.addLayer({
    id: 'osm-poi-label', type: 'symbol', source: 'osm-pois', minzoom: 18,
    filter: ['all', ['!', ['has', 'point_count']], ['has', 'name'], ['!=', ['get', 'natural'], 'peninsula']],
    layout: { 'text-field': ['get', 'name'], 'text-font': ['noto_sans_regular'], 'text-size': 10, 'text-offset': [0, 1.25], 'text-anchor': 'top', 'text-optional': true },
    paint: { 'text-color': '#334155', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 }
  })
  if (!instance.getLayer('osm-selected-point-halo')) instance.addLayer({
    id: 'osm-selected-point-halo', type: 'circle', source: 'osm-pois', minzoom: 11,
    filter: ['all', ['!', ['has', 'point_count']], ['!=', ['get', 'natural'], 'peninsula']],
    paint: {
      'circle-color': '#ffffff', 'circle-radius': 13,
      'circle-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.96, 0]
    }
  })
  if (!instance.getLayer('osm-selected-point')) instance.addLayer({
    id: 'osm-selected-point', type: 'circle', source: 'osm-pois', minzoom: 11,
    filter: ['all', ['!', ['has', 'point_count']], ['!=', ['get', 'natural'], 'peninsula']],
    paint: {
      'circle-color': osmBusinessColorExpression(), 'circle-radius': 9, 'circle-stroke-color': '#154d73', 'circle-stroke-width': 3,
      'circle-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0],
      'circle-stroke-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0]
    }
  })
  updateOsmSelection()
}

function scheduleOsmViewportRefresh(delay = 220, force = false) {
  forceNextOsmRefresh ||= force
  clearTimeout(osmViewportTimer)
  if (!map.value || disposed) return
  osmViewportTimer = setTimeout(() => {
    const forceRefresh = forceNextOsmRefresh
    forceNextOsmRefresh = false
    void refreshOsmViewportForCurrentMap({ force: forceRefresh })
  }, delay)
}

async function refreshOsmViewportForCurrentMap(options: { force?: boolean } = {}) {
  await nextTick()
  const instance = map.value
  const container = mapEl.value
  if (!instance || disposed || !container?.isConnected || container.clientWidth === 0 || container.clientHeight === 0) return
  if (instance.isMoving()) {
    scheduleOsmViewportRefresh(120, options.force === true)
    return
  }
  if (!instance.isStyleLoaded() && !instance.getSource('osm-pois')) return

  const bounds = instance.getBounds()
  const viewport = {
    west: bounds.getWest(), south: bounds.getSouth(),
    east: bounds.getEast(), north: bounds.getNorth()
  }
  const zoom = instance.getZoom()

  if (!options.force && osmStore.covers(viewport, zoom)) return
  const bufferedViewport = expandOsmBounds(viewport)
  const previousData = osmStore.data
  performanceCounters.viewportFetches += 1
  const data = await osmStore.load(bufferedViewport, zoom, options)
  if (!disposed && map.value === instance && data && (options.force || data !== previousData)) updateOsmSources(data)
}

function updateOsmSources(data = osmStore.data) {
  if (!map.value || !data) return
  const started = performance.now()
  const generation = osmStore.generation
  const safeFeatures = data.features.filter(feature => !shouldExcludeOsmFeature(feature))
  const pointFeatures = safeFeatures.filter(feature => feature.properties.feature_type === 'point')
  const polygonFeatures = safeFeatures.filter(feature => feature.properties.feature_type === 'polygon')
  const points: FeatureCollection = { type: 'FeatureCollection', features: pointFeatures } as FeatureCollection
  const polygons: FeatureCollection = { type: 'FeatureCollection', features: polygonFeatures } as FeatureCollection
  if (performanceDebugEnabled) {
    performanceCounters.osmSetDataCalls += 2
    performanceCounters.osmFeatures = safeFeatures.length
    performanceCounters.osmVertices = countVertices({ ...data, features: safeFeatures })
    performanceCounters.osmPayloadBytes = osmStore.viewportCache.get(osmStore.dataRequestKey)?.payloadBytes || 0
  }
  ;(map.value.getSource('osm-pois') as GeoJSONSource | undefined)?.setData(points)
  ;(map.value.getSource('osm-polygons') as GeoJSONSource | undefined)?.setData(polygons)
  if (osmStore.selectedFeature && !safeFeatures.some(feature => feature.properties.feature_id === osmStore.selectedFeature?.properties.feature_id)) {
    mapSelection.clearSelection()
  }
  updateOsmSelection()
  map.value.once('idle', () => {
    if (generation === osmStore.generation) {
      performanceCounters.lastOsmRenderMs = performance.now() - started
      osmStore.setRenderDuration(performanceCounters.lastOsmRenderMs)
    }
  })
}

function updateOsmSelection() {
  if (selectedOsmState && map.value?.getSource(selectedOsmState.source)) {
    map.value.setFeatureState(selectedOsmState, { selected: false })
    selectedOsmState = null
  }
  const feature = osmStore.selectedFeature
  if (feature?.properties.feature_type === 'point' && map.value) {
    selectedOsmState = {
      source: 'osm-pois',
      id: feature.properties.feature_id
    }
    if (map.value.getSource(selectedOsmState.source)) map.value.setFeatureState(selectedOsmState, { selected: true })
  }
}

async function handleMapClick(instance: Map, event: MapMouseEvent) {
  const tolerance = window.matchMedia('(pointer: coarse)').matches ? 12 : 8
  const picked = pickMapEntityAtPoint(instance, event.point, tolerance)
  if (!picked) {
    mapSelection.clearSelection()
    mapStore.closeMobilePanels()
    return
  }

  if (picked.kind === 'point-poi') {
    const featureId = picked.feature.properties?.feature_id
    const feature = osmStore.data?.features.find(item => item.id === featureId)
    if (!feature) return
    const detailRequest = mapSelection.selectOsm(feature)
    if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openMobilePanel('selection')
    await detailRequest
    return
  }

  if (picked.kind === 'cluster' && picked.feature.properties?.cluster_id != null) {
    const source = instance.getSource('osm-pois') as GeoJSONSource
    const zoom = await source.getClusterExpansionZoom(Number(picked.feature.properties.cluster_id))
    const coordinates = picked.feature.geometry.type === 'Point' ? picked.feature.geometry.coordinates : null
    if (coordinates?.[0] != null && coordinates[1] != null) {
      instance.easeTo({ center: [coordinates[0], coordinates[1]], zoom })
    }
    return
  }

  if (picked.kind === 'interactive-polygon') {
    await selectInteractivePolygon(picked.polygon)
  }
}

function handleMapHover(instance: Map, event: MapMouseEvent) {
  pendingHoverPoint = { x: event.point.x, y: event.point.y }
  if (hoverFrame !== undefined) return
  hoverFrame = requestAnimationFrame(() => {
    hoverFrame = undefined
    const point = pendingHoverPoint
    pendingHoverPoint = null
    if (!point || disposed) return
    if (mapDragging) {
      setMapCursor(instance, 'dragging')
      return
    }
    const picked = pickMapEntityAtPoint(instance, point, 4)
    setMapCursor(instance, picked ? 'interactive' : 'pan')
    const polygonId = picked?.kind === 'interactive-polygon' && picked.polygon.target.type === 'polygon'
      ? picked.polygon.id
      : ''
    updatePolygonHover(polygonId || null)
  })
}

function ensureMapInfrastructure(instance: Map) {
  ensureAnalysisAreaInfrastructure(instance)
  ensureOsmInfrastructure(instance)
  ensurePolygonInfrastructure(instance)
  ensureSelectionInfrastructure(instance)
  ensureStadtplanerLayerOrder(instance)
  if (import.meta.dev && !hasValidStadtplanerLayerOrder(instance)) {
    console.warn('Stadtplaner overlay layer order is invalid', getStadtplanerLayerOrder(instance))
  }
}

function ensureAnalysisAreaInfrastructure(instance: Map) {
  if (!instance.getSource('analysis-areas')) instance.addSource('analysis-areas', { type: 'geojson', data: analysisAreasStore.featureCollection })
  const layers = [
    { id: 'analysis-areas-municipality', type: 'MUNICIPALITY', minzoom: 7, maxzoom: 10.5, color: '#2563eb', opacity: 0.035, width: 2.2 },
    { id: 'analysis-areas-district', type: 'DISTRICT', minzoom: 9.5, maxzoom: 13.5, color: '#15803d', opacity: 0.045, width: 1.5 },
    { id: 'analysis-areas-quarter', type: 'QUARTER', minzoom: 11.5, maxzoom: 24, color: '#b45309', opacity: 0.045, width: 1 }
  ] as const
  for (const layer of layers) {
    if (!instance.getLayer(`${layer.id}-fill`)) instance.addLayer({
      id: `${layer.id}-fill`, type: 'fill', source: 'analysis-areas', minzoom: layer.minzoom, maxzoom: layer.maxzoom,
      filter: ['==', ['get', 'area_type'], layer.type], paint: { 'fill-color': layer.color, 'fill-opacity': layer.opacity }
    })
    if (!instance.getLayer(layer.id)) instance.addLayer({
      id: layer.id, type: 'line', source: 'analysis-areas', minzoom: layer.minzoom, maxzoom: layer.maxzoom,
      filter: ['==', ['get', 'area_type'], layer.type], paint: { 'line-color': layer.color, 'line-opacity': 0.72, 'line-width': layer.width }
    })
    if (!instance.getLayer(`${layer.id}-label`)) instance.addLayer({
      id: `${layer.id}-label`, type: 'symbol', source: 'analysis-areas', minzoom: layer.minzoom + 0.8, maxzoom: layer.maxzoom,
      filter: ['==', ['get', 'area_type'], layer.type],
      layout: { 'text-field': ['get', 'name'], 'text-font': ['noto_sans_regular'], 'text-size': layer.type === 'MUNICIPALITY' ? 13 : 11, 'text-optional': true },
      paint: { 'text-color': layer.color, 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 }
    })
  }
  setAnalysisAreaVisibility()
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
  const selected = analysisAreasStore.selectedArea
  if (selected && !analysisAreasStore.visibility[selected.area_type]) mapSelection.clearSelection()
}

function ensurePolygonInfrastructure(instance: Map) {
  if (!instance.getSource('overview-polygons')) instance.addSource('overview-polygons', { type: 'geojson', data: visibleFeatureCollection.value })
  if (!instance.getLayer('overview-polygons-fill')) instance.addLayer({
    id: 'overview-polygons-fill',
    type: 'fill',
    source: 'overview-polygons',
    paint: { 'fill-color': activeThemeColorExpression(), 'fill-opacity': 0.3 }
  })
  if (!instance.getLayer('overview-polygons-line')) instance.addLayer({
    id: 'overview-polygons-line',
    type: 'line',
    source: 'overview-polygons',
    paint: { 'line-color': activeThemeColorExpression(), 'line-width': 2 }
  })
  applyFeatureStyles()
  setPolygonVisibility(mapStore.polygonsVisible)
}

function ensureSelectionInfrastructure(instance: Map) {
  const empty: FeatureCollection = { type: 'FeatureCollection', features: [] }
  if (!instance.getSource('selected-polygon-source')) {
    instance.addSource('selected-polygon-source', { type: 'geojson', data: empty })
  }
  if (!instance.getLayer('selected-polygon-fill')) instance.addLayer({
    id: 'selected-polygon-fill', type: 'fill', source: 'selected-polygon-source',
    paint: { 'fill-color': ['get', 'selection_color'], 'fill-opacity': 0.22 }
  })
  if (!instance.getLayer('selected-polygon-halo')) instance.addLayer({
    id: 'selected-polygon-halo', type: 'line', source: 'selected-polygon-source',
    paint: {
      'line-color': '#ffffff',
      'line-width': ['interpolate', ['linear'], ['zoom'], 7, 4.5, 18, 9],
      'line-opacity': 0.96
    }
  })
  if (!instance.getLayer('selected-polygon-outline')) instance.addLayer({
    id: 'selected-polygon-outline', type: 'line', source: 'selected-polygon-source',
    paint: {
      'line-color': '#154d73',
      'line-width': ['interpolate', ['linear'], ['zoom'], 7, 2.5, 18, 4.5],
      'line-opacity': 1
    }
  })
  updateSelectedPolygonOverlay()
}

async function selectInteractivePolygon(polygon: InteractivePolygonFeature) {
  if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openMobilePanel('selection')
  if (polygon.target.type === 'polygon') {
    await selectPolygon(polygon.id)
    return
  }
  if (polygon.target.type === 'analysis-area') {
    await mapSelection.selectAnalysisArea(polygon.id)
    return
  }
  const feature = osmStore.data?.features.find(item => item.properties.feature_id === polygon.id)
  if (feature) await mapSelection.selectOsm(feature)
  else mapSelection.clearSelection()
}

function updateSelectedPolygonOverlay() {
  const entity = mapStore.selectedMapEntity
  if (!entity) {
    setSelectedPolygonOverlay(null)
    return
  }
  if (entity.type === 'polygon') {
    const polygon = polygonStore.polygons.find(item => item.id === entity.id)
    setSelectedPolygonOverlay(polygon ? {
      id: polygon.id,
      source: 'overview-polygons',
      layerId: 'overview-polygons-fill',
      featureType: 'STADTPLANNER',
      geometryType: polygon.geometry.type,
      selectionKey: `overview-polygons:STADTPLANNER:${polygon.id}`,
      geometry: polygon.geometry,
      properties: { category: polygon.category, occupancy_status: polygon.occupancy_status, size: polygon.area_size, business_structure: polygon.business_structure },
      target: { type: 'polygon', id: polygon.id }
    } : null)
    return
  }
  if (entity.type === 'osm') {
    const feature = entity.feature
    const featureType = feature.properties.category === 'landuse' || feature.properties.category === 'building' ? 'OSM_CONTEXT_POLYGON' : 'OSM_POLYGON'
    setSelectedPolygonOverlay(feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon' ? {
      id: feature.properties.feature_id,
      source: 'osm-polygons',
      layerId: 'osm-polygons-fill',
      featureType,
      geometryType: feature.geometry.type,
      selectionKey: `osm-polygons:${featureType}:${feature.properties.feature_id}`,
      geometry: feature.geometry,
      properties: { category: feature.properties.category, canonical_category: feature.properties.canonical_category },
      target: { type: 'osm', id: feature.properties.feature_id }
    } : null)
    return
  }
  const feature = analysisAreasStore.featureCollection.features.find(item => item.properties.id === entity.id)
  setSelectedPolygonOverlay(feature ? {
    id: entity.id,
    source: 'analysis-areas',
    layerId: `analysis-areas-${feature.properties.area_type.toLowerCase()}-fill`,
    featureType: feature.properties.area_type,
    geometryType: feature.geometry.type,
    selectionKey: `analysis-areas:${feature.properties.area_type}:${entity.id}`,
    geometry: feature.geometry,
    properties: { area_type: feature.properties.area_type },
    target: { type: 'analysis-area', id: entity.id }
  } : null)
}

function setSelectedPolygonOverlay(polygon: InteractivePolygonFeature | null) {
  const source = map.value?.getSource('selected-polygon-source') as GeoJSONSource | undefined
  if (!source) return
  const features = polygon ? [{
    type: 'Feature' as const,
    id: polygon.selectionKey,
    geometry: polygon.geometry,
    properties: {
      id: polygon.id,
      feature_type: polygon.featureType,
      source_type: polygon.source,
      selection_key: polygon.selectionKey,
      selection_color: interactivePolygonColor(polygon)
    }
  }] : []
  source.setData({ type: 'FeatureCollection', features } as FeatureCollection)
}

function interactivePolygonColor(polygon: InteractivePolygonFeature) {
  if (polygon.source === 'analysis-areas') {
    return polygon.featureType === 'MUNICIPALITY' ? '#2563eb' : polygon.featureType === 'DISTRICT' ? '#15803d' : '#b45309'
  }
  const canonicalCategory = polygon.properties?.canonical_category
  if (typeof canonicalCategory === 'string') return getIndustryColor(canonicalCategory)
  const category = polygon.properties?.category
  if (polygon.source === 'overview-polygons' && typeof category === 'string') {
    return thematicColor(mapStore.thematicStyle, polygon.properties || {})
  }
  return typeof category === 'string' ? osmCategoryColors[category] || '#64748b' : '#64748b'
}

async function selectPolygon(id: string, fitSelection = false) {
  const selectionRequest = mapSelection.selectPolygon(id)
  if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openMobilePanel('selection')
  await selectionRequest
  if (mapStore.selectedMapEntity?.type !== 'polygon' || mapStore.selectedMapEntity.id !== id) return
  const bbox = polygonStore.selectedMetrics?.bbox
  if (fitSelection && bbox && map.value) map.value.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
    padding: window.matchMedia('(max-width: 1279px)').matches ? { top: 64, right: 40, bottom: 300, left: 40 } : 72,
    maxZoom: 18,
    duration: 0
  })
}

async function selectRequestedArea(instance: Map) {
  const slug = typeof route.query.area === 'string' ? route.query.area : ''
  const area = analysisAreasStore.areas.find(candidate => candidate.slug === slug)
  if (!area) return
  const request = mapSelection.selectAnalysisArea(area.id)
  if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openMobilePanel('selection')
  const feature = analysisAreasStore.featureCollection.features.find(candidate => candidate.properties.id === area.id)
  const bounds = feature ? geometryBounds(feature.geometry.coordinates) : null
  if (bounds) instance.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], { padding: 72, maxZoom: 16, duration: 0 })
  await request
}

function geometryBounds(coordinates: unknown): [number, number, number, number] | null {
  const bounds: [number, number, number, number] = [Infinity, Infinity, -Infinity, -Infinity]
  const visit = (value: unknown) => {
    if (!Array.isArray(value)) return
    if (typeof value[0] === 'number' && typeof value[1] === 'number') {
      bounds[0] = Math.min(bounds[0], value[0])
      bounds[1] = Math.min(bounds[1], value[1])
      bounds[2] = Math.max(bounds[2], value[0])
      bounds[3] = Math.max(bounds[3], value[1])
      return
    }
    value.forEach(visit)
  }
  visit(coordinates)
  return Number.isFinite(bounds[0]) ? bounds : null
}

async function waitForGisPreviewReady(instance: Map) {
  await nextTick()
  await new Promise<void>((resolve) => {
    if (!instance.isMoving()) {
      requestAnimationFrame(() => resolve())
      return
    }
    instance.once('moveend', () => requestAnimationFrame(() => resolve()))
  })
}

function applyFeatureStyles() {
  if (!map.value?.getLayer('overview-polygons-fill')) return
  const highlighted = mapStore.categoryHighlight || ''
  map.value.setPaintProperty('overview-polygons-fill', 'fill-opacity', [
    'case',
    ['boolean', ['feature-state', 'hovered'], false], 0.46,
    ['==', ['get', 'category'], highlighted], 0.5,
    0.3
  ])
  const color = activeThemeColorExpression()
  map.value.setPaintProperty('overview-polygons-fill', 'fill-color', color)
  map.value.setPaintProperty('overview-polygons-line', 'line-color', color)
  map.value.setPaintProperty('overview-polygons-line', 'line-width', [
    'case', ['boolean', ['feature-state', 'hovered'], false], 3, 2
  ])
}

function updatePolygonHover(id: string | null) {
  if (!map.value || hoveredPolygonId === id) return
  if (hoveredPolygonId) map.value.setFeatureState({ source: 'overview-polygons', id: hoveredPolygonId }, { hovered: false })
  hoveredPolygonId = id
  if (id) map.value.setFeatureState({ source: 'overview-polygons', id }, { hovered: true })
}

function clearSelectionRendering() {
  if (!map.value) return
  if (selectedOsmState) map.value.setFeatureState(selectedOsmState, { selected: false })
  setSelectedPolygonOverlay(null)
}

type ColorExpression = NonNullable<NonNullable<FillLayerSpecification['paint']>['fill-color']>

function osmBusinessColorExpression() {
  return [
    'case',
    ['all', ['has', 'canonical_category'], ['!=', ['get', 'canonical_category'], null]],
    industryColorExpression('canonical_category'),
    osmColorExpression()
  ] as unknown as ColorExpression
}

function activeThemeColorExpression() {
  return thematicColorExpression(mapStore.thematicStyle) as ColorExpression
}

function updateSource(data: FeatureCollection) {
  const source = map.value?.getSource('overview-polygons') as GeoJSONSource | undefined
  if (source && performanceDebugEnabled) performanceCounters.polygonSetDataCalls += 1
  source?.setData(data)
}

function countVertices(data: OsmViewportResult) {
  let count = 0
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      count += 1
      return
    }
    for (const child of value) visit(child)
  }
  for (const feature of data.features) visit(feature.geometry.coordinates)
  return count
}

function installPerformanceDebug(instance: Map) {
  if (!import.meta.client || !performanceDebugEnabled) return
  window.__stadtplanerMapPerformance = {
    map: instance,
    counters: performanceCounters,
    reset() {
      performanceCounters.viewportFetches = 0
      performanceCounters.osmSetDataCalls = 0
      performanceCounters.polygonSetDataCalls = 0
    },
    snapshot() {
      const bounds = instance.getBounds()
      return {
        ...performanceCounters,
        sources: Object.keys(instance.getStyle().sources).length,
        layers: instance.getStyle().layers.length,
        zoom: instance.getZoom(),
        viewportCovered: Number(osmStore.covers({
          west: bounds.getWest(), south: bounds.getSouth(),
          east: bounds.getEast(), north: bounds.getNorth()
        }, instance.getZoom())),
        loadedWest: osmStore.loadedBounds?.west || 0,
        loadedEast: osmStore.loadedBounds?.east || 0
      }
    },
    getLayerOrder: () => getStadtplanerLayerOrder(instance)
  }
}

declare global {
  interface Window {
    __stadtplanerMapPerformance?: {
      map: Map
      counters: typeof performanceCounters
      reset: () => void
      snapshot: () => Record<string, number>
      getLayerOrder: () => string[]
    }
  }
}

function setPolygonVisibility(visible: boolean) {
  if (!map.value) return
  const visibility = visible ? 'visible' : 'none'
  for (const layer of ['overview-polygons-fill', 'overview-polygons-line']) {
    if (map.value.getLayer(layer)) map.value.setLayoutProperty(layer, 'visibility', visibility)
  }
  if (!visible && mapStore.selectedMapEntity?.type === 'polygon') mapSelection.clearSelection()
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

<style scoped>
:deep(.maplibregl-ctrl-attrib a) {
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>
