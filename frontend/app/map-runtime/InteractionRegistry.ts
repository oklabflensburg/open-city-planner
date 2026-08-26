import type { Map as MapLibreMap } from 'maplibre-gl'
import type { MapContext, MapInteractionContribution, MapInteractionEvent, MapInteractionEventName } from '#frontend-module-sdk'
import { MapRuntimeError } from './errors'

type MapEventHandler = (event: unknown) => void

export class InteractionRegistry {
  readonly #definitions = new Map<string, MapInteractionContribution>()
  readonly #mapHandlers = new Map<MapInteractionEventName, MapEventHandler>()
  #map: MapLibreMap | null = null
  #context: MapContext | null = null

  register(contribution: MapInteractionContribution) {
    if (this.#definitions.has(contribution.id)) throw new MapRuntimeError(`Map interaction "${contribution.id}" is already registered.`)
    this.#definitions.set(contribution.id, contribution)
    if (this.#map) this.#reattachEvent(contribution.event)
    return () => this.unregister(contribution.id)
  }

  unregister(id: string) {
    const event = this.#definitions.get(id)?.event
    this.#definitions.delete(id)
    if (event && this.#map) this.#reattachEvent(event)
  }

  attach(map: MapLibreMap, context: MapContext) {
    this.detach()
    this.#map = map
    this.#context = context
    for (const event of new Set([...this.#definitions.values()].map(item => item.event))) this.#attachEvent(event)
  }

  detach() {
    if (this.#map) {
      for (const [event, handler] of this.#mapHandlers) {
        if (event === 'keydown') this.#map.getCanvas().removeEventListener('keydown', handler as EventListener)
        else this.#map.off(event as 'click', handler)
      }
    }
    this.#mapHandlers.clear()
    this.#map = null
    this.#context = null
  }

  #reattachEvent(event: MapInteractionEventName) {
    const previous = this.#mapHandlers.get(event)
    if (previous && this.#map) {
      if (event === 'keydown') this.#map.getCanvas().removeEventListener('keydown', previous as EventListener)
      else this.#map.off(event as 'click', previous)
      this.#mapHandlers.delete(event)
    }
    if ([...this.#definitions.values()].some(item => item.event === event)) this.#attachEvent(event)
  }

  #attachEvent(event: MapInteractionEventName) {
    if (!this.#map || this.#mapHandlers.has(event)) return
    const handler: MapEventHandler = rawEvent => { void this.#dispatch(event, rawEvent) }
    this.#mapHandlers.set(event, handler)
    if (event === 'keydown') {
      const canvas = this.#map.getCanvas()
      if (!canvas.hasAttribute('tabindex')) canvas.tabIndex = 0
      canvas.addEventListener('keydown', handler as EventListener)
    } else {
      this.#map.on(event as 'click', handler)
    }
  }

  async #dispatch(type: MapInteractionEventName, rawEvent: unknown) {
    if (!this.#map || !this.#context) return
    const candidates = [...this.#definitions.values()]
      .filter(item => item.event === type && item.enabled?.() !== false)
      .sort((left, right) => (left.priority ?? 100) - (right.priority ?? 100) || left.id.localeCompare(right.id, 'en'))
    const eventRecord = rawEvent && typeof rawEvent === 'object' ? rawEvent as Record<string, unknown> : {}
    for (const contribution of candidates) {
      let features: readonly unknown[] | undefined
      if (contribution.layerIds?.length) {
        const point = eventRecord.point
        if (!point) continue
        const available = contribution.layerIds.filter(id => this.#map?.getLayer(id))
        if (!available.length) continue
        features = this.#context.features.queryRendered({ point: point as never, layerIds: available })
        if (!features.length) continue
      }
      const event: MapInteractionEvent = {
        type,
        point: eventRecord.point as MapInteractionEvent['point'],
        lngLat: eventRecord.lngLat as MapInteractionEvent['lngLat'],
        originalEvent: (eventRecord.originalEvent ?? rawEvent) as Event,
        features
      }
      const result = await contribution.handler(event, this.#context)
      if (result?.handled) break
    }
  }
}
