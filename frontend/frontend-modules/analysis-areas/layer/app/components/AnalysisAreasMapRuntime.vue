<template>
  <span class="sr-only">Analysegebiete sind auf der Karte verfügbar.</span>
</template>

<script setup lang="ts">
import type { MapContext, MapFeatureInfoProvider, MapSelectionPresentation } from '#frontend-module-sdk'
import { useMapContext, useMapFilterPort } from '#frontend-module-sdk'
import { onBeforeUnmount, watch } from 'vue'
import { useAnalysisAreasStore } from '../stores/analysisAreas'

interface RenderedAreaFeature {
  readonly id?: string | number
  readonly properties?: Readonly<Record<string, unknown>>
  readonly geometry?: GeoJSON.Geometry
}

const mapContext = useMapContext()
const areas = useAnalysisAreasStore()
const route = useRoute()
const filter = useMapFilterPort()
const filterQuery = computed(() => filter.toQuery().toString())
let unregisterInteraction: (() => void) | undefined
let unregisterFeatureInfo: (() => void) | undefined
let unregisterPresentation: (() => void) | undefined

const layerIds = [
  'analysis-areas.quarter-fill',
  'analysis-areas.district-fill',
  'analysis-areas.municipality-fill'
]

const featureInfo: MapFeatureInfoProvider = {
  id: 'analysis-areas.feature-info',
  moduleId: 'analysis-areas',
  canHandle: selection => selection.moduleId === 'analysis-areas',
  resolveFeatureInfo: selection => ({
    id: String(selection.featureId),
    name: String(selection.properties?.name || 'Analysegebiet'),
    areaType: String(selection.properties?.area_type || '')
  })
}

const presentation: MapSelectionPresentation = {
  id: 'analysis-areas.selection',
  moduleId: 'analysis-areas',
  canPresent: selection => selection.moduleId === 'analysis-areas',
  present: selection => areas.presentSelection(String(selection.featureId)),
  clear: () => areas.clearSelection()
}

function source(context: MapContext) {
  return context.unsafeMapLibre().getSource('analysis-areas.data')
}

function updateSource(context: MapContext) {
  const current = source(context)
  if (current && 'setData' in current && typeof current.setData === 'function') {
    current.setData(areas.featureCollection)
  }
}

function updateVisibility(context: MapContext) {
  const map = context.unsafeMapLibre()
  for (const [type, suffix] of [
    ['MUNICIPALITY', 'municipality'],
    ['DISTRICT', 'district'],
    ['QUARTER', 'quarter']
  ] as const) {
    const visibility = areas.visibility[type] ? 'visible' : 'none'
    for (const ending of ['-fill', '', '-label']) {
      const id = `analysis-areas.${suffix}${ending}`
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visibility)
    }
  }
}

function coordinates(geometry: GeoJSON.Geometry): number[][] {
  if (geometry.type === 'Polygon') return geometry.coordinates.flat()
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.flat(2)
  return []
}

function fitFeature(context: MapContext, feature: RenderedAreaFeature) {
  if (!feature.geometry) return
  const points = coordinates(feature.geometry)
  if (!points.length) return
  const longitudes = points.map(point => point[0]!).filter(Number.isFinite)
  const latitudes = points.map(point => point[1]!).filter(Number.isFinite)
  if (!longitudes.length || !latitudes.length) return
  context.map.fitBounds(
    [[Math.min(...longitudes), Math.min(...latitudes)], [Math.max(...longitudes), Math.max(...latitudes)]],
    { padding: 48, maxZoom: 16, duration: 0 }
  )
}

async function selectFeature(feature: RenderedAreaFeature, context: MapContext) {
  const id = String(feature.properties?.id || feature.id || '')
  if (!id) return
  const request = context.selection.select({
    moduleId: 'analysis-areas',
    sourceId: 'analysis-areas.data',
    layerId: String((feature.properties?.area_type || 'area')).toLowerCase(),
    featureId: id,
    properties: feature.properties,
    geometry: feature.geometry
  })
  if (import.meta.client && window.matchMedia('(max-width: 1279px)').matches) {
    context.selection.reveal()
  }
  await request
}

async function selectRequestedArea(context: MapContext) {
  const requested = typeof route.query.gebiet === 'string'
    ? route.query.gebiet
    : typeof route.query.area === 'string' ? route.query.area : ''
  if (!requested) return
  const area = areas.areas.find(candidate => candidate.slug === requested)
  const feature = areas.featureCollection.features.find(candidate => candidate.properties.id === area?.id)
  if (!area || !feature) return
  fitFeature(context, feature)
  await selectFeature(feature, context)
}

async function register(context: MapContext) {
  await areas.load()
  updateSource(context)
  updateVisibility(context)
  unregisterPresentation = context.selection.registerPresentation(presentation)
  unregisterFeatureInfo = context.featureInfo.register(featureInfo)
  unregisterInteraction = context.interactions.register({
    id: 'analysis-areas.select',
    moduleId: 'analysis-areas',
    event: 'click',
    layerIds,
    priority: 20,
    handler: async (event, activeContext) => {
      const feature = event.features?.[0] as RenderedAreaFeature | undefined
      if (!feature) return
      await selectFeature(feature, activeContext)
      return { handled: true }
    }
  })
  await selectRequestedArea(context)
}

watch(mapContext, (context) => {
  unregisterInteraction?.()
  unregisterFeatureInfo?.()
  unregisterPresentation?.()
  unregisterInteraction = undefined
  unregisterFeatureInfo = undefined
  unregisterPresentation = undefined
  if (context) void register(context)
}, { immediate: true })

watch(() => areas.featureCollection, () => {
  if (mapContext.value) updateSource(mapContext.value)
}, { deep: true })

watch(() => areas.visibility, () => {
  if (mapContext.value) updateVisibility(mapContext.value)
}, { deep: true })

watch(filterQuery, () => {
  if (areas.selectedAreaId) void areas.loadDetails()
})

watch(() => [route.query.gebiet, route.query.area], () => {
  if (mapContext.value) void selectRequestedArea(mapContext.value)
})

onBeforeUnmount(() => {
  unregisterInteraction?.()
  unregisterFeatureInfo?.()
  unregisterPresentation?.()
})
</script>
