import type { FeatureCollection } from 'geojson'
import type { FillLayerSpecification, GeoJSONSource, Map, MapMouseEvent } from 'maplibre-gl'
import type { OsmViewportResult } from '~/types/osm'
import { getIndustryColor, industryColorExpression } from '~/utils/industries'
import { thematicColor, thematicColorExpression } from '~/utils/mapThemes'
import { osmCategoryColors, osmColorExpression } from '~/utils/osmCategories'
import { shouldExcludeOsmFeature } from '~/utils/osmExclusions'
import { pickMapEntityAtPoint, type InteractivePolygonFeature } from '~/utils/mapFeaturePicking'
import { ensureStadtplanerLayerOrder, getStadtplanerLayerOrder, hasValidStadtplanerLayerOrder } from '~/utils/mapLayerOrder'
import { setMapCursor } from '~/utils/mapCursor'
import { getMapViewportPadding } from '~/utils/mapViewportPadding'
import { loadMapStyle } from '~/config/mapStyles'
import type { MapContext, MapInteractionEvent } from '#frontend-module-sdk'
import { MAP_CONTEXT_KEY } from '../../module-host/map-vue'
import { createMapRuntime, resolveMapExtensionSnapshot } from '~/map-runtime/MapRuntime'

/**
 * Temporary legacy-domain adapter. Remove domain sections through #108/#137 after
 * their modules consume the public MapContext; the MapLibre lifecycle is host-owned.
 */
export function useMapCanvasHost() {
  const config = useRuntimeConfig()
  const mapStore = useMapStore()
  const polygonStore = usePolygonStore()
  const filterStore = useFilterStore()
  const osmStore = useOsmViewportStore()
  const mapSelection = useMapSelection()
  const route = useRoute()
  const mapEl = ref<HTMLDivElement | null>(null)
  const map = shallowRef<Map | null>(null)
  const mapError = ref('')
  const initialCenter: [number, number] = [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)]
  const initialZoom = Number(config.public.mapZoom)
  let disposed = false
  let layersReady = false
  let initialMapLoadComplete = false
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

  const configuredExtensions = resolveMapExtensionSnapshot(config.public.frontendMapContributions)
  const runtime = createMapRuntime({
    onSelection: {
      onSelect: selection => {
        mapStore.setRuntimeSelection(selection)
        mapStore.selectedMapEntity = null
        polygonStore.clearSelection()
        osmStore.clearSelection()
      },
      onClear: () => mapStore.setRuntimeSelection(null),
      onReveal: () => mapStore.openGisPanel('selection')
    },
    extensions: configuredExtensions,
    createResizeObserver: handler => new ResizeObserver(handler),
    createMap: async (container) => {
      const [maplibregl, mapStyle, , worker] = await Promise.all([
        import('maplibre-gl'),
        loadMapStyle(String(config.public.mapStyleUrl || '')),
        import('maplibre-gl/dist/maplibre-gl.css'),
        import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')
      ])
      maplibregl.setWorkerUrl(worker.default)
      return new maplibregl.Map({
        container,
        style: mapStyle,
        center: mapStore.center,
        zoom: mapStore.zoom,
        bearing: mapStore.bearing,
        pitch: mapStore.pitch,
        attributionControl: { compact: true },
        canvasContextAttributes: { powerPreference: 'high-performance' }
      })
    }
  })
  const runtimeContext = shallowRef<MapContext | null>(null)
  let disconnectRuntimeSelection: (() => void) | undefined
  provide(MAP_CONTEXT_KEY, runtimeContext)

  runtime.interactions.register({
    id: 'host.entity-selection',
    moduleId: 'host',
    event: 'click',
    priority: 10,
    handler: async (event, context) => ({
      handled: await handleMapClick(context.unsafeMapLibre(), event)
    })
  })
  runtime.interactions.register({
    id: 'host.clear-selection',
    moduleId: 'host',
    event: 'click',
    priority: 10_000,
    handler: () => {
      mapSelection.clearSelection()
      mapStore.closeGisPanels()
      return { handled: true }
    }
  })

  const visibleFeatureCollection = computed<FeatureCollection>(() => polygonStore.featureCollection as FeatureCollection)
  const showEmptyState = computed(() => osmStore.poi
    ? !osmStore.loading && (osmStore.data?.meta.count || 0) === 0
    : filterStore.activeFilterCount > 0 && filterStore.selectedSources.length > 0
    && !polygonStore.loading && !osmStore.loading
    && polygonStore.polygons.length === 0 && (osmStore.data?.meta.business_count || 0) === 0)

  runtime.onReady(async (instance, reason) => {
    if (disposed) return
    if (reason === 'load') {
      ensureMapInfrastructure(instance)
      runtime.layers.ensureOrder()
      layersReady = true
      mapStore.mapLoaded = true
      mapError.value = ''
      await polygonStore.loadPolygons()
      updateSource(visibleFeatureCollection.value)
      const requested = await requestedPolygonId()
      if (requested) await selectPolygon(requested, true)
      await refreshOsmViewportForCurrentMap({ force: true })
      mapStore.markGisDataFresh()
      initialMapLoadComplete = true
      return
    }
    ensureMapInfrastructure(instance)
    runtime.layers.ensureOrder()
    layersReady = true
    mapStore.mapLoaded = true
    mapError.value = ''
    if (!initialMapLoadComplete) return
    updateSource(visibleFeatureCollection.value)
    void refreshOsmViewportForCurrentMap({ force: true })
  })

  onMounted(async () => {
    disconnectRuntimeSelection = mapStore.connectRuntimeSelection(
      () => runtime.selection.clear(),
      selection => runtime.selection.select(selection)
    )
    if (!mapEl.value) return
    mapStore.mapLoaded = false
    try {
      const container = mapEl.value
      if (disposed || !container?.isConnected) return
      const instance = await runtime.start(container)
      if (!instance || disposed) return
      map.value = markRaw(instance)
      runtimeContext.value = runtime.context()
      setMapCursor(instance, 'pan')
      installPerformanceDebug(instance)
      instance.touchZoomRotate.enable()
      instance.dragRotate.enable()
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
        if (!layersReady) mapError.value = 'Die Kartenbasis konnte nicht vollständig geladen werden.'
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
    }
    runtime.destroy()
    disconnectRuntimeSelection?.()
    disconnectRuntimeSelection = undefined
    runtimeContext.value = null
    map.value = null
    if (import.meta.client) delete (window as typeof window & { __stadtplanerMapPerformance?: unknown }).__stadtplanerMapPerformance
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
  watch(() => mapStore.runtimeSelection, updateSelectedPolygonOverlay)
  watch(() => mapStore.categoryHighlight, applyFeatureStyles)
  watch(() => mapStore.thematicStyle, () => {
    applyFeatureStyles()
    updateSelectedPolygonOverlay()
  })
  watch(() => mapStore.polygonsVisible, setPolygonVisibility)
  watch(
    () => [osmStore.showPois, osmStore.showAreas, osmStore.showBuildings, osmStore.activeCategories.join(','), osmStore.poi],
    () => scheduleOsmViewportRefresh(0)
  )
  watch(() => [route.query.polygon, route.query.flaeche], async () => {
    if (!mapStore.mapLoaded || !map.value) return
    const polygonId = await requestedPolygonId()
    if (polygonId) await selectPolygon(polygonId, true)
    await refreshOsmViewportForCurrentMap({ force: true })
  })

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
    clearTimeout(osmViewportTimer)
    if (!initialMapLoadComplete || !map.value || disposed) return
    forceNextOsmRefresh ||= force
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

  async function handleMapClick(instance: Map, event: MapInteractionEvent) {
    if (!event.point) return false
    const tolerance = window.matchMedia('(pointer: coarse)').matches ? 12 : 8
    const picked = pickMapEntityAtPoint(instance, event.point, tolerance)
    if (!picked) return false

    if (picked.kind === 'point-poi') {
      const featureId = picked.feature.properties?.feature_id
      const feature = osmStore.data?.features.find(item => item.id === featureId)
      if (!feature) return true
      const detailRequest = mapSelection.selectOsm(feature)
      if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openGisPanel('selection')
      await detailRequest
      return true
    }

    if (picked.kind === 'cluster' && picked.feature.properties?.cluster_id != null) {
      const source = instance.getSource('osm-pois') as GeoJSONSource
      const zoom = await source.getClusterExpansionZoom(Number(picked.feature.properties.cluster_id))
      const coordinates = picked.feature.geometry.type === 'Point' ? picked.feature.geometry.coordinates : null
      if (coordinates?.[0] != null && coordinates[1] != null) {
        instance.easeTo({ center: [coordinates[0], coordinates[1]], zoom })
      }
      return true
    }

    if (picked.kind === 'interactive-polygon') {
      await selectInteractivePolygon(picked.polygon)
    }
    return true
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
    ensureOsmInfrastructure(instance)
    ensurePolygonInfrastructure(instance)
    ensureSelectionInfrastructure(instance)
    ensureStadtplanerLayerOrder(instance)
    if (import.meta.dev && !hasValidStadtplanerLayerOrder(instance)) {
      console.warn('Stadtplaner overlay layer order is invalid', getStadtplanerLayerOrder(instance))
    }
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
    if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openGisPanel('selection')
    if (polygon.target.type === 'polygon') {
      await selectPolygon(polygon.id)
      return
    }
    const feature = osmStore.data?.features.find(item => item.properties.feature_id === polygon.id)
    if (feature) await mapSelection.selectOsm(feature)
    else mapSelection.clearSelection()
  }

  function updateSelectedPolygonOverlay() {
    const entity = mapStore.selectedMapEntity
    const runtimeSelection = mapStore.runtimeSelection
    if (!entity && !runtimeSelection) {
      setSelectedPolygonOverlay(null)
      return
    }
    if (entity?.type === 'polygon') {
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
    if (entity?.type === 'osm') {
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
    if (!runtimeSelection || (runtimeSelection.geometry?.type !== 'Polygon' && runtimeSelection.geometry?.type !== 'MultiPolygon')) {
      setSelectedPolygonOverlay(null)
      return
    }
    const featureType = String(runtimeSelection.properties?.area_type || runtimeSelection.layerId)
    setSelectedPolygonOverlay({
      id: String(runtimeSelection.featureId),
      source: runtimeSelection.sourceId,
      layerId: runtimeSelection.layerId,
      featureType,
      geometryType: runtimeSelection.geometry.type,
      selectionKey: `${runtimeSelection.moduleId}:${runtimeSelection.layerId}:${runtimeSelection.featureId}`,
      geometry: runtimeSelection.geometry,
      properties: runtimeSelection.properties || null,
      target: { type: 'module', id: String(runtimeSelection.featureId) }
    })
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
    if (window.matchMedia('(max-width: 1279px)').matches) mapStore.openGisPanel('selection')
    await selectionRequest
    if (mapStore.selectedMapEntity?.type !== 'polygon' || mapStore.selectedMapEntity.id !== id) return
    const bbox = polygonStore.selectedMetrics?.bbox
    if (fitSelection && bbox && map.value) map.value.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
      padding: currentViewportPadding(),
      maxZoom: 18,
      duration: 0
    })
  }

  async function requestedPolygonId() {
    const legacyId = typeof route.query.polygon === 'string' ? route.query.polygon : ''
    if (legacyId && polygonStore.polygons.some(polygon => polygon.id === legacyId)) return legacyId
    const slug = typeof route.query.flaeche === 'string' ? route.query.flaeche : ''
    if (!slug) return ''
    const existing = polygonStore.polygons.find(polygon => polygon.slug === slug)
    if (existing) return existing.id
    try {
      const detail = await usePolygonApi().bySlug(slug)
      polygonStore.polygons = markRaw([...polygonStore.polygons, {
        id: detail.id,
        slug: detail.slug,
        name: detail.name,
        category: detail.category,
        floor: detail.floor,
        area_size: detail.area_size,
        address_display_name: detail.address_display_name,
        occupancy_status: detail.occupancy_status,
        business_structure: detail.business_structure,
        geometry: detail.geometry,
        created_at: detail.created_at,
        updated_at: detail.updated_at
      }])
      return detail.id
    } catch {
      return ''
    }
  }

  function resetVisibleFilters() {
    osmStore.clearPoi()
    filterStore.reset()
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
    ;(window as typeof window & { __stadtplanerMapPerformance?: unknown }).__stadtplanerMapPerformance = {
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

  function setPolygonVisibility(visible: boolean) {
    if (!map.value) return
    const visibility = visible ? 'visible' : 'none'
    for (const layer of ['overview-polygons-fill', 'overview-polygons-line']) {
      if (map.value.getLayer(layer)) map.value.setLayoutProperty(layer, 'visibility', visibility)
    }
    if (!visible && mapStore.selectedMapEntity?.type === 'polygon') mapSelection.clearSelection()
  }

  function resetView() {
    map.value?.easeTo({ center: initialCenter, zoom: initialZoom, bearing: 0, pitch: 0, padding: currentViewportPadding() })
  }

  function currentViewportPadding() {
    const compactPanel = window.matchMedia('(min-width: 900px) and (max-width: 1279px) and (min-height: 560px)').matches
    return getMapViewportPadding({
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      leftPanelExpanded: false,
      bottomSheetOpen: !compactPanel && window.innerWidth < 1280 && mapStore.activeGisPanel !== null,
      compactPanelOpen: compactPanel && mapStore.activeGisPanel !== null,
      analysisPanelVisible: window.innerWidth >= 1280
    })
  }

  function resizeMap() {
    runtime.resize()
  }

  function resizeAfterOrientationChange() {
    window.setTimeout(resizeMap, 180)
  }

  function retryMap() {
    window.location.reload()
  }

  return {
    mapEl,
    map,
    mapError,
    mapStore,
    polygonStore,
    showEmptyState,
    resetView,
    resetVisibleFilters,
    retryMap
  }
}
