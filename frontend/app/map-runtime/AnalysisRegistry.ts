import type { MapAnalysisProvider, MapContext } from '#frontend-module-sdk'
import { MapRuntimeError } from './errors'

export class AnalysisRegistry {
  readonly #providers = new Map<string, MapAnalysisProvider>()

  register(provider: MapAnalysisProvider) {
    if (this.#providers.has(provider.id)) throw new MapRuntimeError(`Map analysis provider "${provider.id}" is already registered.`)
    this.#providers.set(provider.id, provider)
    return () => this.unregister(provider.id)
  }

  unregister(id: string) {
    this.#providers.delete(id)
  }

  analyze(id: string, input: unknown, context: MapContext) {
    const provider = this.#providers.get(id)
    if (!provider) throw new MapRuntimeError(`Unknown map analysis provider "${id}".`)
    return provider.analyze(input, context)
  }

  clear() {
    this.#providers.clear()
  }
}
