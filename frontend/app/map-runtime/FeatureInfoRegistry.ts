import type { MapContext, MapFeatureInfoProvider, SelectedMapFeature } from '#frontend-module-sdk'
import { MapRuntimeError } from './errors'

export class FeatureInfoRegistry {
  readonly #providers = new Map<string, MapFeatureInfoProvider>()

  register(provider: MapFeatureInfoProvider) {
    if (this.#providers.has(provider.id)) throw new MapRuntimeError(`Feature-info provider "${provider.id}" is already registered.`)
    this.#providers.set(provider.id, provider)
    return () => this.unregister(provider.id)
  }

  unregister(id: string) {
    this.#providers.delete(id)
  }

  async resolve(selection: SelectedMapFeature, context: MapContext) {
    const provider = [...this.#providers.values()]
      .filter(candidate => candidate.canHandle(selection))
      .sort((left, right) => (left.priority ?? 100) - (right.priority ?? 100) || left.id.localeCompare(right.id, 'en'))[0]
    return provider ? provider.resolveFeatureInfo(selection, context) : undefined
  }

  clear() {
    this.#providers.clear()
  }
}
