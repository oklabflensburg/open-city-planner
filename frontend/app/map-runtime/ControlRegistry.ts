import type { IControl, Map as MapLibreMap } from 'maplibre-gl'
import type { MapContext, MapControlContribution } from '#frontend-module-sdk'
import { MapRuntimeError } from './errors'

export class ControlRegistry {
  readonly #definitions = new Map<string, MapControlContribution>()
  readonly #attached = new Map<string, ReturnType<MapControlContribution['create']>>()
  #map: MapLibreMap | null = null
  #context: MapContext | null = null

  register(contribution: MapControlContribution) {
    if (!contribution.accessibleLabel.trim()) throw new MapRuntimeError(`Map control "${contribution.id}" requires an accessible label.`)
    if (this.#definitions.has(contribution.id)) throw new MapRuntimeError(`Map control "${contribution.id}" is already registered.`)
    this.#definitions.set(contribution.id, contribution)
    if (this.#map && this.#context) this.#attachOne(contribution)
    return () => this.unregister(contribution.id)
  }

  attach(map: MapLibreMap, context: MapContext) {
    this.detach()
    this.#map = map
    this.#context = context
    for (const contribution of this.#ordered()) this.#attachOne(contribution)
  }

  unregister(id: string) {
    const control = this.#attached.get(id)
    if (control && this.#map) this.#map.removeControl(control)
    this.#attached.delete(id)
    this.#definitions.delete(id)
  }

  detach() {
    if (this.#map) for (const control of this.#attached.values()) this.#map.removeControl(control)
    this.#attached.clear()
    this.#map = null
    this.#context = null
  }

  #ordered() {
    return [...this.#definitions.values()].sort((left, right) =>
      (left.priority ?? 100) - (right.priority ?? 100) || left.id.localeCompare(right.id, 'en'))
  }

  #attachOne(contribution: MapControlContribution) {
    if (!this.#map || !this.#context || this.#attached.has(contribution.id)) return
    const control = contribution.create(this.#context)
    const accessibleControl: IControl = {
      onAdd: (map) => {
        const element = control.onAdd(map)
        if (!element.hasAttribute('aria-label')) element.setAttribute('aria-label', contribution.accessibleLabel)
        return element
      },
      onRemove: map => control.onRemove(map),
      getDefaultPosition: control.getDefaultPosition?.bind(control)
    }
    this.#map.addControl(accessibleControl, contribution.position)
    this.#attached.set(contribution.id, accessibleControl)
  }
}
