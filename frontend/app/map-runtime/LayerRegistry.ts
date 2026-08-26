import type { LayerSpecification, Map as MapLibreMap, SourceSpecification } from 'maplibre-gl'
import type { BoundMapLayerContribution, BoundMapSourceContribution } from '#frontend-module-sdk'
import { MAP_LAYER_GROUPS } from '../../module-host/map-contract'
import {
  DuplicateMapLayerError,
  DuplicateMapSourceError,
  MapExtensionError,
  MapRegistrySealedError,
  UnknownMapSourceError
} from './errors'

export class LayerRegistry {
  readonly #sources = new Map<string, BoundMapSourceContribution>()
  readonly #layers = new Map<string, BoundMapLayerContribution>()
  #map: MapLibreMap | null = null
  #sealed = false

  registerSource(contribution: BoundMapSourceContribution) {
    if (this.#sealed) throw new MapRegistrySealedError(contribution.id)
    if (this.#sources.has(contribution.id)) throw new DuplicateMapSourceError(contribution.id)
    this.#sources.set(contribution.id, contribution)
    return () => this.unregisterSource(contribution.id)
  }

  registerLayer(contribution: BoundMapLayerContribution) {
    if (this.#sealed) throw new MapRegistrySealedError(contribution.id)
    if (this.#layers.has(contribution.id)) throw new DuplicateMapLayerError(contribution.id)
    if (!this.#sources.has(contribution.sourceId)) throw new UnknownMapSourceError(contribution.sourceId, contribution.id)
    this.#layers.set(contribution.id, contribution)
    return () => this.unregisterLayer(contribution.id)
  }

  seal() {
    this.#sealed = true
    return this
  }

  attach(map: MapLibreMap) {
    this.#map = map
    const started = performance.now()
    for (const contribution of this.#sources.values()) {
      if (!map.getSource(contribution.id)) {
        try {
          map.addSource(contribution.id, contribution.source as SourceSpecification)
        } catch (error) {
          throw new MapExtensionError(contribution.id, error)
        }
      }
    }
    for (const contribution of this.orderedLayers()) {
      if (!map.getLayer(contribution.id)) {
        const specification = {
          ...contribution.layer,
          id: contribution.id,
          source: contribution.sourceId,
          layout: {
            ...('layout' in contribution.layer ? contribution.layer.layout : {}),
            ...(contribution.visible === false ? { visibility: 'none' } : {})
          }
        } as LayerSpecification
        try {
          map.addLayer(specification)
        } catch (error) {
          throw new MapExtensionError(contribution.id, error)
        }
      }
    }
    this.ensureOrder()
    return performance.now() - started
  }

  orderedLayers() {
    return [...this.#layers.values()].sort((left, right) => {
      const group = MAP_LAYER_GROUPS.indexOf(left.group) - MAP_LAYER_GROUPS.indexOf(right.group)
      if (group) return group
      const priority = (left.priority ?? 100) - (right.priority ?? 100)
      if (priority) return priority
      const moduleOrder = left.moduleOrder - right.moduleOrder
      return moduleOrder || left.id.localeCompare(right.id, 'en')
    })
  }

  ensureOrder() {
    if (!this.#map) return
    for (const group of MAP_LAYER_GROUPS) {
      let beforeId = nextLegacyAnchor(this.#map, group)
      const groupLayers = this.orderedLayers().filter(layer => layer.group === group)
      for (const contribution of groupLayers.reverse()) {
        if (!this.#map.getLayer(contribution.id)) continue
        this.#map.moveLayer(contribution.id, beforeId)
        beforeId = contribution.id
      }
    }
  }

  unregisterLayer(id: string) {
    if (this.#map?.getLayer(id)) this.#map.removeLayer(id)
    this.#layers.delete(id)
  }

  unregisterSource(id: string) {
    for (const layer of [...this.#layers.values()]) {
      if (layer.sourceId === id) this.unregisterLayer(layer.id)
    }
    if (this.#map?.getSource(id)) this.#map.removeSource(id)
    this.#sources.delete(id)
  }

  unregisterOwner(moduleId: string) {
    for (const layer of [...this.#layers.values()]) if (layer.moduleId === moduleId) this.unregisterLayer(layer.id)
    for (const source of [...this.#sources.values()]) if (source.moduleId === moduleId) this.unregisterSource(source.id)
  }

  detach() {
    if (this.#map) {
      for (const layer of [...this.orderedLayers()].reverse()) if (this.#map.getLayer(layer.id)) this.#map.removeLayer(layer.id)
      for (const source of this.#sources.values()) if (this.#map.getSource(source.id)) this.#map.removeSource(source.id)
    }
    this.#map = null
  }

  source(id: string) {
    return this.#map?.getSource(id)
  }
}

const LEGACY_ANCHORS: Partial<Record<(typeof MAP_LAYER_GROUPS)[number], readonly string[]>> = {
  analysis: ['osm-polygons-fill', 'overview-polygons-fill', 'selected-polygon-fill', 'osm-clusters', 'osm-poi-circle', 'osm-poi-label'],
  'osm-polygons': ['overview-polygons-fill', 'selected-polygon-fill', 'osm-clusters', 'osm-poi-circle', 'osm-poi-label'],
  'cityplanner-polygons': ['selected-polygon-fill', 'osm-clusters', 'osm-poi-circle', 'osm-poi-label'],
  selection: ['osm-clusters', 'osm-poi-circle', 'osm-poi-label'],
  'poi-clusters': ['osm-poi-circle', 'osm-poi-label'],
  pois: ['osm-poi-label']
}

function nextLegacyAnchor(map: MapLibreMap, group: (typeof MAP_LAYER_GROUPS)[number]) {
  return LEGACY_ANCHORS[group]?.find(id => map.getLayer(id))
}
