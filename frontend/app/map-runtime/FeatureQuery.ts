import type { Map as MapLibreMap } from 'maplibre-gl'
import type { MapFeatureQueryApi, MapFeatureQueryOptions } from '#frontend-module-sdk'

export class FeatureQuery implements MapFeatureQueryApi {
  readonly #map: MapLibreMap

  constructor(map: MapLibreMap) {
    this.#map = map
  }

  queryRendered(options: MapFeatureQueryOptions) {
    const layers = options.layerIds.filter(id => this.#map.getLayer(id))
    if (!layers.length) return []
    const geometry = options.bbox ?? options.point
    if (!geometry) return []
    return this.#map.queryRenderedFeatures(geometry as never, { layers })
  }
}
