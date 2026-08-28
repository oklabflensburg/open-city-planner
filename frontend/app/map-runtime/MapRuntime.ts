import type { Map as MapLibreMap } from 'maplibre-gl'
import type {
  BoundMapLayerContribution,
  BoundMapSourceContribution,
  MapContext
} from '#frontend-module-sdk'
import { AnalysisRegistry } from './AnalysisRegistry'
import { ControlRegistry } from './ControlRegistry'
import { DrawManager } from './DrawManager'
import { FeatureInfoRegistry } from './FeatureInfoRegistry'
import { FeatureQuery } from './FeatureQuery'
import { InteractionRegistry } from './InteractionRegistry'
import { LayerRegistry } from './LayerRegistry'
import { MapLifecycle, type MapLifecycleOptions, type MapReadyHandler } from './MapLifecycle'
import { createMapFacade } from './MapFacade'
import { MapTelemetry } from './MapTelemetry'
import { SelectionManager } from './SelectionManager'

export interface MapExtensionSnapshot {
  readonly sources: readonly BoundMapSourceContribution[]
  readonly layers: readonly BoundMapLayerContribution[]
}

const EMPTY_MAP_EXTENSION_SNAPSHOT: MapExtensionSnapshot = Object.freeze({
  sources: Object.freeze([]),
  layers: Object.freeze([])
})

export function resolveMapExtensionSnapshot(value: unknown): MapExtensionSnapshot {
  if (!value || typeof value !== 'object') return EMPTY_MAP_EXTENSION_SNAPSHOT
  const snapshot = value as Partial<MapExtensionSnapshot>
  return {
    sources: Array.isArray(snapshot.sources) ? snapshot.sources : EMPTY_MAP_EXTENSION_SNAPSHOT.sources,
    layers: Array.isArray(snapshot.layers) ? snapshot.layers : EMPTY_MAP_EXTENSION_SNAPSHOT.layers
  }
}

export interface CreateMapRuntimeOptions extends MapLifecycleOptions {
  readonly extensions?: MapExtensionSnapshot
  readonly reportTelemetry?: ConstructorParameters<typeof MapTelemetry>[0]
  readonly onSelection?: ConstructorParameters<typeof SelectionManager>[0]
}

export class MapRuntime {
  readonly lifecycle: MapLifecycle
  readonly layers = new LayerRegistry()
  readonly controls = new ControlRegistry()
  readonly interactions = new InteractionRegistry()
  readonly selection: SelectionManager
  readonly draw = new DrawManager()
  readonly featureInfo = new FeatureInfoRegistry()
  readonly analysis = new AnalysisRegistry()
  readonly telemetry: MapTelemetry
  #context: MapContext | null = null
  #started = false

  constructor(options: CreateMapRuntimeOptions) {
    this.lifecycle = new MapLifecycle(options)
    this.selection = new SelectionManager(options.onSelection)
    this.telemetry = new MapTelemetry(options.reportTelemetry)
    for (const source of options.extensions?.sources ?? []) this.layers.registerSource(source)
    for (const layer of options.extensions?.layers ?? []) this.layers.registerLayer(layer)
    this.layers.seal()
    this.lifecycle.onReady(async (map, reason) => {
      await this.telemetry.measure(reason === 'load' ? 'map.init' : 'map.style-ready', () => {
        try {
          this.telemetry.record('map.layer-registration', this.layers.attach(map))
        } catch (error) {
          console.error('Map extension attachment failed', error)
        }
        if (!this.#context) return
        if (reason === 'load') {
          this.controls.attach(map, this.#context)
          this.interactions.attach(map, this.#context)
        }
      })
    })
  }

  onReady(handler: MapReadyHandler) {
    return this.lifecycle.onReady(handler)
  }

  async start(container: HTMLElement) {
    if (this.#started) return this.lifecycle.map()
    this.#started = true
    const map = await this.lifecycle.create(container)
    this.#context = this.#createContext(map)
    return map
  }

  context() {
    return this.#context
  }

  resize() {
    this.lifecycle.resize()
  }

  destroy() {
    this.interactions.detach()
    this.controls.detach()
    this.featureInfo.clear()
    this.analysis.clear()
    this.selection.destroy()
    this.draw.destroy()
    this.layers.detach()
    this.lifecycle.destroy()
    this.#context = null
    this.#started = false
  }

  #createContext(map: MapLibreMap): MapContext {
    return Object.freeze({
      map: createMapFacade(map),
      selection: this.selection,
      draw: this.draw,
      features: new FeatureQuery(map),
      controls: this.controls,
      interactions: this.interactions,
      featureInfo: this.featureInfo,
      analysis: this.analysis,
      telemetry: this.telemetry,
      unsafeMapLibre: () => map
    })
  }
}

export function createMapRuntime(options: CreateMapRuntimeOptions) {
  return new MapRuntime(options)
}
