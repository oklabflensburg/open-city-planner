import type {
  IControl,
  LayerSpecification,
  LngLatLike,
  LngLatBoundsLike,
  Map as MapLibreMap,
  PointLike,
  SourceSpecification
} from 'maplibre-gl'

export const MAP_LAYER_GROUPS = [
  'analysis',
  'osm-polygons',
  'cityplanner-polygons',
  'selection',
  'poi-clusters',
  'pois',
  'labels',
  'overlay'
] as const

export const MAP_INTERACTION_EVENTS = [
  'click',
  'dblclick',
  'contextmenu',
  'mousemove',
  'mouseenter',
  'mouseleave',
  'keydown'
] as const

export type MapLayerGroup = typeof MAP_LAYER_GROUPS[number]
export type MapInteractionEventName = typeof MAP_INTERACTION_EVENTS[number]
export type MapControlPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
export type MapLayerDefinition = LayerSpecification extends infer Layer
  ? Layer extends LayerSpecification ? Omit<Layer, 'id' | 'source'> : never
  : never

export interface MapSourceContribution {
  readonly id: string
  readonly source: SourceSpecification
}

export interface MapLayerContribution {
  readonly id: string
  readonly sourceId: string
  readonly layer: MapLayerDefinition
  readonly group: MapLayerGroup
  readonly priority?: number
  readonly visible?: boolean
}

export interface FrontendModuleMapContributions {
  readonly sources: readonly MapSourceContribution[]
  readonly layers: readonly MapLayerContribution[]
}

export interface BoundMapSourceContribution extends MapSourceContribution {
  readonly moduleId: string
  readonly moduleOrder: number
}

export interface BoundMapLayerContribution extends MapLayerContribution {
  readonly moduleId: string
  readonly moduleOrder: number
}

export interface MapFacade {
  getCenter(): { lng: number, lat: number }
  getZoom(): number
  fitBounds(bounds: LngLatBoundsLike, options?: Readonly<Record<string, unknown>>): void
  flyTo(options: Readonly<Record<string, unknown>>): void
  project(position: LngLatLike): { x: number, y: number }
  unproject(point: PointLike): { lng: number, lat: number }
}

export interface MapFeatureQueryOptions {
  readonly point?: PointLike
  readonly bbox?: readonly [PointLike, PointLike]
  readonly layerIds: readonly string[]
}

export interface MapFeatureQueryApi {
  queryRendered(options: MapFeatureQueryOptions): readonly unknown[]
}

export interface MapTelemetry {
  measure<T>(name: string, operation: () => T | Promise<T>): Promise<T>
  record(name: string, durationMs: number): void
}

export interface SelectedMapFeature {
  readonly moduleId: string
  readonly sourceId: string
  readonly layerId: string
  readonly featureId: string | number
  readonly properties?: Readonly<Record<string, unknown>>
  readonly geometry?: GeoJSON.Geometry
}

export interface MapSelectionPresentation {
  readonly id: string
  readonly moduleId: string
  readonly priority?: number
  canPresent(selection: SelectedMapFeature): boolean
  present(selection: SelectedMapFeature): void | Promise<void>
  clear?(): void
}

export interface MapInteractionEvent {
  readonly type: MapInteractionEventName
  readonly point?: { x: number, y: number }
  readonly lngLat?: { lng: number, lat: number }
  readonly features?: readonly unknown[]
  readonly originalEvent?: Event
}

export interface MapInteractionResult {
  readonly handled?: boolean
}

export interface MapInteractionContribution {
  readonly id: string
  readonly moduleId: string
  readonly event: MapInteractionEventName
  readonly layerIds?: readonly string[]
  readonly priority?: number
  readonly enabled?: () => boolean
  readonly handler: (event: MapInteractionEvent, context: MapContext) => void | MapInteractionResult | Promise<void | MapInteractionResult>
}

export interface MapControlContribution {
  readonly id: string
  readonly moduleId: string
  readonly position: MapControlPosition
  readonly priority?: number
  readonly accessibleLabel: string
  readonly create: (context: MapContext) => IControl
}

export interface MapControlRegistryApi {
  register(contribution: MapControlContribution): () => void
}

export interface MapInteractionRegistryApi {
  register(contribution: MapInteractionContribution): () => void
}

export interface MapFeatureInfoProvider<T = unknown> {
  readonly id: string
  readonly moduleId: string
  readonly priority?: number
  canHandle(selection: SelectedMapFeature): boolean
  resolveFeatureInfo(selection: SelectedMapFeature, context: MapContext): T | Promise<T>
}

export interface MapFeatureInfoRegistryApi {
  register(provider: MapFeatureInfoProvider): () => void
}

export interface MapAnalysisProvider<TInput = unknown, TResult = unknown> {
  readonly id: string
  readonly moduleId: string
  analyze(input: TInput, context: MapContext): TResult | Promise<TResult>
}

export interface MapAnalysisRegistryApi {
  register(provider: MapAnalysisProvider): () => void
}

export interface DrawAdapter {
  start(): void
  stop(): void
  setMode(mode: string): void
  clear(): void
  destroy(): void
}

export interface DrawManagerApi {
  initialize(factory: () => DrawAdapter): DrawAdapter
  startMode(mode: string): void
  stop(): void
  clear(): void
}

export interface SelectionManagerApi {
  current(): SelectedMapFeature | null
  select(selection: SelectedMapFeature): Promise<void>
  clear(): void
}

export interface MapContext {
  readonly map: MapFacade
  readonly selection: SelectionManagerApi
  readonly draw: DrawManagerApi
  readonly features: MapFeatureQueryApi
  readonly controls: MapControlRegistryApi
  readonly interactions: MapInteractionRegistryApi
  readonly featureInfo: MapFeatureInfoRegistryApi
  readonly analysis: MapAnalysisRegistryApi
  readonly telemetry: MapTelemetry
  /** Explicit escape hatch for APIs that the stable facade intentionally omits. */
  unsafeMapLibre(): MapLibreMap
}
