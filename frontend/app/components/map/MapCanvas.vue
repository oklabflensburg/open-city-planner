<template>
  <div class="relative h-full min-h-[420px] overflow-hidden rounded-[16px] border border-white bg-white shadow-[0_1px_12px_rgba(20,24,28,0.08)]">
    <div ref="mapEl" class="absolute inset-0 h-full w-full" />
    <div class="pointer-events-none absolute left-3 top-3 z-10">
      <MapControls @zoom-in="map?.zoomIn()" @zoom-out="map?.zoomOut()" @reset="resetView" />
    </div>
    <div class="pointer-events-none absolute right-3 top-3 z-10">
      <MapLayerControl @toggle-polygons="setLayerVisibility('demo-polygons', $event)" @toggle-drawings="setLayerVisibility('user-polygons-fill', $event)" />
    </div>
    <div class="pointer-events-none absolute bottom-3 left-1/2 z-10 -translate-x-1/2">
      <DrawingToolbar />
    </div>
    <div v-if="polygonStore.error" class="absolute bottom-16 left-3 z-10 max-w-[320px] rounded-lg bg-white px-3 py-2 text-xs text-red-700 shadow">
      {{ polygonStore.error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { GeoJSONSource, Map, MapLayerMouseEvent } from 'maplibre-gl'
import type { TerraDraw } from 'terra-draw'
import { industries, industryColors } from '~/utils/industries'
import type { PolygonGeometry, UserPolygon } from '~/types/geo'
import type { FeatureCollection } from 'geojson'

const config = useRuntimeConfig()
const mapStore = useMapStore()
const polygonStore = usePolygonStore()
const filterStore = useFilterStore()
const authStore = useAuthStore()
const route = useRoute()
const mapEl = ref<HTMLDivElement | null>(null)
const map = shallowRef<Map | null>(null)
const draw = shallowRef<TerraDraw | null>(null)
const pendingGeometryDrafts = new globalThis.Map<string, PolygonGeometry>()
const activeEditFeatureId = ref<string | null>(null)
const initialCenter: [number, number] = [Number(config.public.mapCenterLng), Number(config.public.mapCenterLat)]
const initialZoom = Number(config.public.mapZoom)

const demoPolygons = [
  demoPolygon('demo-1', 'fashion', [[[9.4327, 54.7848], [9.4337, 54.7852], [9.4340, 54.7847], [9.4330, 54.7843], [9.4327, 54.7848]]]),
  demoPolygon('demo-2', 'food', [[[9.4356, 54.7838], [9.4364, 54.7841], [9.4366, 54.7836], [9.4358, 54.7833], [9.4356, 54.7838]]]),
  demoPolygon('demo-3', 'warehouse', [[[9.4340, 54.7860], [9.4352, 54.7864], [9.4354, 54.7858], [9.4342, 54.7854], [9.4340, 54.7860]]])
]

const newestMaterializedDemoPolygonById = computed(() => {
  const newestByDemoId = new globalThis.Map<string, UserPolygon>()

  for (const polygon of polygonStore.polygons) {
    const demoId = polygon.properties.demoId
    if (typeof demoId !== 'string') continue

    const current = newestByDemoId.get(demoId)
    if (!current || isNewerPolygon(polygon, current)) {
      newestByDemoId.set(demoId, polygon)
    }
  }

  return newestByDemoId
})

const materializedDemoIds = computed(() => new Set(newestMaterializedDemoPolygonById.value.keys()))

const visibleUserPolygonIds = computed(() => {
  const ids = new Set(polygonStore.polygons.map((polygon) => polygon.id))

  for (const polygon of polygonStore.polygons) {
    const demoId = polygon.properties.demoId
    if (typeof demoId === 'string' && newestMaterializedDemoPolygonById.value.get(demoId)?.id !== polygon.id) {
      ids.delete(polygon.id)
    }
  }

  return ids
})

const demoFeatureCollection = computed(() => ({
  type: 'FeatureCollection' as const,
  features: demoPolygons.filter((feature) => (
    !materializedDemoIds.value.has(feature.id)
    && filterStore.activeCategories.includes(feature.properties.category as never)
    && normalizeSize(feature.properties.size) === filterStore.selectedSize
    && normalizeFloor(feature.properties.floor) === filterStore.selectedFloor
  ))
}))

function demoPolygon(id: string, category: string, coordinates: PolygonGeometry['coordinates']) {
  const label = industries.find((industry) => industry.key === category)?.label || category
  return {
    type: 'Feature' as const,
    id,
    geometry: { type: 'Polygon' as const, coordinates },
    properties: { id, category, name: label, size: 'M', floor: 'EG' }
  }
}

function normalizeSize(value: unknown) {
  return ['S', 'M', 'L', 'XL'].includes(String(value)) ? String(value) : 'M'
}

function normalizeFloor(value: unknown) {
  return ['UG', 'EG', 'OG'].includes(String(value)) ? String(value) : 'EG'
}

const userFeatureCollection = computed(() => ({
  type: 'FeatureCollection' as const,
  features: polygonStore.featureCollection.features.filter((feature) => (
    typeof feature.id !== 'string' || visibleUserPolygonIds.value.has(feature.id)
  )).filter((feature) => (
    feature.properties.category ? filterStore.activeCategories.includes(feature.properties.category as never) : true
  )).filter((feature) => (
    normalizeSize((feature.properties as Record<string, unknown>).size) === filterStore.selectedSize
    && normalizeFloor((feature.properties as Record<string, unknown>).floor) === filterStore.selectedFloor
  )).filter((feature) => (
    mapStore.activeMode !== 'edit' || feature.id !== polygonStore.selectedPolygonId
  ))
}))

onMounted(async () => {
  if (!mapEl.value) return

  mapStore.center = initialCenter
  mapStore.zoom = initialZoom

  try {
    const maplibregl = await import('maplibre-gl')
    const instance = new maplibregl.Map({
      container: mapEl.value,
      style: String(config.public.versatilesStyleUrl),
      center: initialCenter,
      zoom: initialZoom,
      bearing: 0,
      pitch: 0,
      attributionControl: { compact: true }
    })

    map.value = instance
    instance.touchZoomRotate.enable()
    instance.dragRotate.enable()

    instance.on('load', async () => {
      mapStore.mapLoaded = true
      addPolygonLayers(instance)
      void initTerraDraw(instance)
      await polygonStore.loadPolygons()
      const requestedPolygon = typeof route.query.polygon === 'string' ? route.query.polygon : ''
      if (requestedPolygon && polygonStore.polygons.some(polygon => polygon.id === requestedPolygon)) {
        await polygonStore.selectPolygon(requestedPolygon)
        mapStore.analysisDrawerOpen = true
        const bbox = polygonStore.selectedMetrics?.bbox
        if (bbox) {
          instance.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 72, maxZoom: 18 })
        }
      }
      requestAnimationFrame(() => instance.resize())
    })

    instance.on('error', (event) => {
      console.warn('MapLibre resource error', event.error)
    })

    instance.on('moveend', () => {
      mapStore.setView(
        [instance.getCenter().lng, instance.getCenter().lat],
        instance.getZoom(),
        instance.getBearing(),
        instance.getPitch()
      )
    })

    instance.on('click', 'user-polygons-fill', (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id
      if (id && mapStore.activeMode === 'delete') {
        const polygon = polygonStore.polygons.find((item) => item.id === String(id))
        if (!canEditPolygon(polygon)) {
          polygonStore.error = authStore.authenticated ? 'Du kannst nur eigene Flächen löschen.' : 'Bitte melde dich zum Bearbeiten an.'
          mapStore.setMode('select')
          return
        }
        void polygonStore.deletePolygon(String(id)).then(() => {
          mapStore.setMode('select')
          mapStore.analysisDrawerOpen = false
        })
        return
      }
      if (id) {
        void polygonStore.selectPolygon(String(id))
        mapStore.analysisDrawerOpen = true
      }
    })

    instance.on('click', 'demo-polygons', (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id
      if (id && mapStore.activeMode === 'select') {
        void materializeDemoPolygon(String(id))
      }
    })

    requestAnimationFrame(() => instance.resize())
    window.addEventListener('resize', resizeMap)
  } catch (error) {
    polygonStore.error = error instanceof Error ? error.message : 'Die Kartenbibliothek konnte nicht geladen werden.'
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeMap)
  pendingGeometryDrafts.clear()
  draw.value?.stop()
  map.value?.remove()
})

watch(userFeatureCollection, (collection) => updateSource('user-polygons', collection), { deep: true })
watch(demoFeatureCollection, (collection) => updateSource('demo-polygons', collection), { deep: true })
watch(() => polygonStore.selectedPolygonId, applyFeatureState)
watch(() => polygonStore.selectedPolygon, (selected) => {
  if (!selected) {
    removeEditFeature()
    refreshUserPolygons()
    return
  }
  syncSelectedPolygonToDraw()
})
watch(() => polygonStore.selectedPolygon?.category, () => syncSelectedPolygonToDraw())
watch(() => mapStore.categoryHighlight, applyCategoryFilter)
watch(() => mapStore.activeMode, (mode, previousMode) => {
  if (previousMode === 'edit' && mode !== 'edit' && polygonStore.selectedPolygonId) {
    completeGeometryUpdate(polygonStore.selectedPolygonId)
  }
  if (mode !== 'select' && !authStore.canWrite) {
    mapStore.setMode('select')
    return
  }
  if (!draw.value) return
  const terraMode = mode === 'polygon' ? 'polygon' : 'select'
  draw.value.setMode(terraMode)
  if (mode === 'edit') {
    syncSelectedPolygonToDraw()
  } else {
    removeEditFeature()
    refreshUserPolygons()
  }
})

function addPolygonLayers(instance: Map) {
  instance.addSource('demo-polygons', { type: 'geojson', data: demoFeatureCollection.value })
  instance.addLayer({
    id: 'demo-polygons',
    type: 'fill',
    source: 'demo-polygons',
    paint: {
      'fill-color': categoryColorExpression(),
      'fill-opacity': ['case', ['==', ['get', 'category'], mapStore.categoryHighlight || ''], 0.78, 0.58]
    }
  })
  instance.addLayer({
    id: 'demo-polygons-line',
    type: 'line',
    source: 'demo-polygons',
    paint: { 'line-color': '#ffffff', 'line-width': 1.2 }
  })
  instance.addSource('user-polygons', { type: 'geojson', data: userFeatureCollection.value })
  instance.addLayer({
    id: 'user-polygons-fill',
    type: 'fill',
    source: 'user-polygons',
    paint: {
      'fill-color': categoryColorExpression(),
      'fill-opacity': ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], 0.42, 0.24]
    }
  })
  instance.addLayer({
    id: 'user-polygons-line',
    type: 'line',
    source: 'user-polygons',
    paint: {
      'line-color': ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], '#111111', categoryColorExpression()],
      'line-width': ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], 3, 1.8]
    }
  })
}

function categoryColorExpression() {
  return ['match', ['get', 'category'], ...Object.entries(industryColors).flat(), '#9b9b9b'] as any
}

function categoryColor(category: string) {
  return (industryColors[category as keyof typeof industryColors] || '#9b9b9b') as `#${string}`
}

async function initTerraDraw(instance: Map) {
  const [{ TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode }, { TerraDrawMapLibreGLAdapter }] = await Promise.all([
    import('terra-draw'),
    import('terra-draw-maplibre-gl-adapter')
  ])

  const terra = new TerraDraw({
    adapter: new TerraDrawMapLibreGLAdapter({ map: instance }),
    modes: [
      new TerraDrawSelectMode({
        flags: {
          polygon: {
            feature: { draggable: true, rotateable: true, scaleable: true, coordinates: { midpoints: true, draggable: true, deletable: true } }
          }
        }
      }),
      new TerraDrawPolygonMode({ styles: { fillColor: '#154d73', outlineColor: '#154d73', fillOpacity: 0.24, outlineWidth: 2 } })
    ]
  })

  terra.on('finish', async (id: string | number) => {
    if (mapStore.activeMode !== 'polygon' || !authStore.canWrite) return
    const feature = terra.getSnapshotFeature(id)
    if (feature?.geometry.type === 'Polygon') {
      const polygon = await polygonStore.createPolygon({
        name: 'Meine Verkaufsfläche',
        category: 'custom',
        description: '',
        geometry: feature.geometry as PolygonGeometry,
        properties: {}
      })
      terra.removeFeatures([id])
      await polygonStore.selectPolygon(polygon.id)
      mapStore.setMode('select')
      mapStore.analysisDrawerOpen = true
    }
  })

  terra.on('change', (ids: Array<string | number>, type: string) => {
    if (type !== 'update' || mapStore.activeMode !== 'edit') return
    const id = ids[0]
    if (id === undefined) return
    const feature = terra.getSnapshotFeature(id)
    const selected = polygonStore.selectedPolygon
    if (selected && String(id) === selected.id && feature?.geometry.type === 'Polygon') {
      stageGeometryUpdate(selected.id, feature.geometry as PolygonGeometry)
    }
  })

  terra.on('deselect', (id: string | number) => {
    if (mapStore.activeMode !== 'edit' || String(id) !== polygonStore.selectedPolygonId) return
    completeGeometryUpdate(String(id))
    mapStore.setMode('select')
    refreshUserPolygons()
  })

  terra.start()
  draw.value = terra
}

function stageGeometryUpdate(id: string, geometry: PolygonGeometry) {
  const polygon = polygonStore.polygons.find((item) => item.id === id)
  if (!canEditPolygon(polygon)) {
    polygonStore.error = authStore.authenticated ? 'Du kannst nur eigene Flächen bearbeiten.' : 'Bitte melde dich zum Bearbeiten an.'
    mapStore.setMode('select')
    return
  }
  polygonStore.polygons = polygonStore.polygons.map((polygon) => (
    polygon.id === id ? { ...polygon, geometry } : polygon
  ))
  pendingGeometryDrafts.set(id, geometry)
}

function completeGeometryUpdate(id: string) {
  const geometry = pendingGeometryDrafts.get(id)
  if (!geometry || !polygonStore.polygons.some(polygon => polygon.id === id)) return
  pendingGeometryDrafts.delete(id)
  void polygonStore.updatePolygon(id, { geometry }).catch((error) => {
    if (error instanceof Error && error.message.includes('404')) {
      polygonStore.polygons = polygonStore.polygons.filter((polygon) => polygon.id !== id)
      polygonStore.clearSelection()
      return
    }
    polygonStore.error = error instanceof Error ? error.message : 'Polygon konnte nicht aktualisiert werden.'
  })
}

async function materializeDemoPolygon(id: string) {
  if (!authStore.canWrite) {
    polygonStore.error = authStore.authenticated ? 'Bitte bestätige zuerst deine E-Mail-Adresse.' : 'Bitte melde dich zum Bearbeiten an.'
    return
  }

  const existing = newestMaterializedDemoPolygonById.value.get(id)
  if (existing) {
    await polygonStore.selectPolygon(existing.id)
    mapStore.analysisDrawerOpen = true
    return
  }

  const feature = demoPolygons.find((polygon) => polygon.id === id)
  if (!feature) return

  const polygon = await polygonStore.createPolygon({
    name: String(feature.properties.name),
    category: String(feature.properties.category),
    description: '',
    geometry: feature.geometry,
    properties: { demoId: feature.id }
  })

  await polygonStore.selectPolygon(polygon.id)
  mapStore.analysisDrawerOpen = true
}

function canEditPolygon(polygon: UserPolygon | undefined) {
  if (!polygon || !authStore.canWrite) return false
  return authStore.user?.is_superuser
    || authStore.user?.roles?.some(role => role.trim().toUpperCase() === 'VERWALTUNG')
    || polygon.created_by_user_id === authStore.user?.id
}

function syncSelectedPolygonToDraw() {
  const terra = draw.value
  const selected = polygonStore.selectedPolygon
  if (!terra || mapStore.activeMode !== 'edit' || !selected) return
  if (activeEditFeatureId.value && activeEditFeatureId.value !== selected.id) {
    removeEditFeature()
  }

  const feature = {
    type: 'Feature' as const,
    id: selected.id,
    geometry: selected.geometry,
    properties: {
      mode: 'polygon',
      id: selected.id,
      name: selected.name,
      category: selected.category
    }
  }
  const color = categoryColor(selected.category)
  terra.setModeStyles('select', {
    selectedPolygonColor: color,
    selectedPolygonOutlineColor: color
  })

  if (terra.hasFeature(selected.id)) {
    const current = terra.getSnapshotFeature(selected.id)
    const currentCategory = (current?.properties as Record<string, unknown> | undefined)?.category
    if (currentCategory !== selected.category) {
      terra.removeFeatures([selected.id])
      terra.addFeatures([feature])
      terra.selectFeature(selected.id)
    } else if (current?.geometry.type !== 'Polygon' || !geometriesEqual(current.geometry as PolygonGeometry, selected.geometry)) {
      terra.updateFeatureGeometry(selected.id, selected.geometry)
    }
  } else {
    terra.addFeatures([feature])
    terra.selectFeature(selected.id)
  }
  activeEditFeatureId.value = selected.id
}

function isNewerPolygon(candidate: UserPolygon, current: UserPolygon) {
  return Date.parse(candidate.updated_at) >= Date.parse(current.updated_at)
}

function geometriesEqual(left: PolygonGeometry, right: PolygonGeometry) {
  return JSON.stringify(left.coordinates) === JSON.stringify(right.coordinates)
}

function removeEditFeature() {
  const terra = draw.value
  const id = activeEditFeatureId.value
  if (terra && id && terra.hasFeature(id)) {
    terra.removeFeatures([id])
  }
  activeEditFeatureId.value = null
}

function updateSource(id: string, data: FeatureCollection) {
  const source = map.value?.getSource(id) as GeoJSONSource | undefined
  source?.setData(data)
}

function refreshUserPolygons() {
  void nextTick(() => {
    updateSource('user-polygons', userFeatureCollection.value)
    applyFeatureState()
  })
}

function applyFeatureState() {
  if (!map.value?.getLayer('user-polygons-fill')) return
  map.value.setPaintProperty('user-polygons-fill', 'fill-opacity', ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], 0.42, 0.24])
  map.value.setPaintProperty('user-polygons-line', 'line-color', ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], '#111111', categoryColorExpression()])
  map.value.setPaintProperty('user-polygons-line', 'line-width', ['case', ['==', ['get', 'id'], polygonStore.selectedPolygonId || ''], 3, 1.8])
}

function applyCategoryFilter() {
  if (!map.value?.getLayer('demo-polygons')) return
  map.value.setPaintProperty('demo-polygons', 'fill-opacity', ['case', ['==', ['get', 'category'], mapStore.categoryHighlight || ''], 0.78, 0.58])
}

function setLayerVisibility(layerId: string, visible: boolean) {
  if (!map.value) return
  const visibility = visible ? 'visible' : 'none'
  map.value.setLayoutProperty(layerId, 'visibility', visibility)
  const lineLayer = layerId === 'demo-polygons' ? 'demo-polygons-line' : 'user-polygons-line'
  map.value.setLayoutProperty(lineLayer, 'visibility', visibility)
}

function resetView() {
  map.value?.easeTo({ center: initialCenter, zoom: initialZoom, bearing: 0, pitch: 0 })
}

function resizeMap() {
  map.value?.resize()
}
</script>
