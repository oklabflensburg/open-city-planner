import type { ResolvedFrontendModule } from './contract.ts'
import {
  MAP_LAYER_GROUPS,
  type BoundMapLayerContribution,
  type BoundMapSourceContribution,
  type MapLayerContribution,
  type MapSourceContribution
} from './map-contract.ts'

export class MapExtensionDefinitionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MapExtensionDefinitionError'
  }
}

export class MapExtensionDefinitionRegistry {
  readonly #sources = new Map<string, BoundMapSourceContribution>()
  readonly #layers = new Map<string, BoundMapLayerContribution>()
  #sealed = false

  registrar(moduleId: string, moduleOrder: number) {
    return {
      registerSource: (source: MapSourceContribution) => this.#registerSource(moduleId, moduleOrder, source),
      registerLayer: (layer: MapLayerContribution) => this.#registerLayer(moduleId, moduleOrder, layer)
    } as const
  }

  seal() {
    this.#sealed = true
    return this
  }

  snapshot() {
    if (!this.#sealed) throw new MapExtensionDefinitionError('Map extension definition registry must be sealed before reading.')
    return Object.freeze({
      sources: Object.freeze([...this.#sources.values()]),
      layers: Object.freeze([...this.#layers.values()].sort(compareMapLayers))
    })
  }

  #registerSource(moduleId: string, moduleOrder: number, source: MapSourceContribution) {
    this.#assertMutable(source.id)
    assertOwnedId(moduleId, source.id, 'source')
    const sourceType = (source.source as { type?: unknown }).type
    if (typeof sourceType !== 'string' || !['geojson', 'vector', 'raster', 'raster-dem', 'image', 'video'].includes(sourceType)) {
      throw new MapExtensionDefinitionError(`Map source "${source.id}" requires a supported declarative source type.`)
    }
    const previous = this.#sources.get(source.id)
    if (previous) throw new MapExtensionDefinitionError(`Duplicate map source "${source.id}" from modules "${previous.moduleId}" and "${moduleId}".`)
    this.#sources.set(source.id, deepFreeze({ ...source, moduleId, moduleOrder }))
  }

  #registerLayer(moduleId: string, moduleOrder: number, layer: MapLayerContribution) {
    this.#assertMutable(layer.id)
    assertOwnedId(moduleId, layer.id, 'layer')
    if ('id' in layer.layer || 'source' in layer.layer) {
      throw new MapExtensionDefinitionError(`Map layer "${layer.id}" must declare ID and source ownership outside its layer definition.`)
    }
    if (!this.#sources.has(layer.sourceId)) throw new MapExtensionDefinitionError(`Map layer "${layer.id}" references unknown source "${layer.sourceId}".`)
    if (!MAP_LAYER_GROUPS.includes(layer.group)) throw new MapExtensionDefinitionError(`Map layer "${layer.id}" uses unknown group "${layer.group}".`)
    const previous = this.#layers.get(layer.id)
    if (previous) throw new MapExtensionDefinitionError(`Duplicate map layer "${layer.id}" from modules "${previous.moduleId}" and "${moduleId}".`)
    this.#layers.set(layer.id, deepFreeze({ ...layer, moduleId, moduleOrder }))
  }

  #assertMutable(id: string) {
    if (this.#sealed) throw new MapExtensionDefinitionError(`Cannot register map extension "${id}" after the registry was sealed.`)
  }
}

export function createMapExtensionDefinitionRegistry(modules: readonly ResolvedFrontendModule[]) {
  const registry = new MapExtensionDefinitionRegistry()
  modules.forEach((module, moduleOrder) => {
    const registrar = registry.registrar(module.id, moduleOrder)
    for (const source of module.publicContributions.map.sources) registrar.registerSource(source)
    for (const layer of module.publicContributions.map.layers) registrar.registerLayer(layer)
  })
  return registry.seal()
}

export function compareMapLayers(left: BoundMapLayerContribution, right: BoundMapLayerContribution) {
  const group = MAP_LAYER_GROUPS.indexOf(left.group) - MAP_LAYER_GROUPS.indexOf(right.group)
  if (group) return group
  const priority = (left.priority ?? 100) - (right.priority ?? 100)
  if (priority) return priority
  const moduleOrder = left.moduleOrder - right.moduleOrder
  return moduleOrder || left.id.localeCompare(right.id, 'en')
}

function assertOwnedId(moduleId: string, id: string, kind: string) {
  if (!id.startsWith(`${moduleId}.`) || !/^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$/.test(id)) {
    throw new MapExtensionDefinitionError(`Map ${kind} "${id}" must use the stable owner prefix "${moduleId}.".`)
  }
}

function deepFreeze<T>(value: T): T {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value
  for (const nested of Object.values(value)) deepFreeze(nested)
  return Object.freeze(value)
}
