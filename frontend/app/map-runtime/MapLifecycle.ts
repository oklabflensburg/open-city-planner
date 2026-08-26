import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapRuntimeError } from './errors'

export type MapFactory = (container: HTMLElement) => MapLibreMap | Promise<MapLibreMap>
export type MapReadyHandler = (map: MapLibreMap, reason: 'load' | 'style.load') => void | Promise<void>

export interface MapLifecycleOptions {
  readonly createMap: MapFactory
  readonly createResizeObserver?: (handler: () => void) => { observe(target: Element): void, disconnect(): void }
  readonly scheduleFrame?: (handler: () => void) => number
  readonly cancelFrame?: (id: number) => void
}

export class MapLifecycle {
  readonly #options: MapLifecycleOptions
  readonly #readyHandlers = new Set<MapReadyHandler>()
  #map: MapLibreMap | null = null
  #resizeObserver: ReturnType<NonNullable<MapLifecycleOptions['createResizeObserver']>> | null = null
  #resizeFrame: number | null = null
  #destroyed = false

  constructor(options: MapLifecycleOptions) {
    this.#options = options
  }

  onReady(handler: MapReadyHandler) {
    this.#readyHandlers.add(handler)
    return () => this.#readyHandlers.delete(handler)
  }

  async create(container: HTMLElement) {
    if (this.#map) throw new MapRuntimeError('MapLifecycle already owns a map.')
    this.#destroyed = false
    const map = await this.#options.createMap(container)
    if (this.#destroyed) {
      map.remove()
      throw new MapRuntimeError('MapLifecycle was destroyed while creating the map.')
    }
    this.#map = map
    map.on('load', this.#handleLoad)
    map.on('style.load', this.#handleStyleLoad)
    if (this.#options.createResizeObserver) {
      this.#resizeObserver = this.#options.createResizeObserver(() => this.resize())
      this.#resizeObserver.observe(container)
    }
    return map
  }

  resize() {
    if (!this.#map) return
    const schedule = this.#options.scheduleFrame ?? (handler => requestAnimationFrame(handler))
    const cancel = this.#options.cancelFrame ?? (id => cancelAnimationFrame(id))
    if (this.#resizeFrame !== null) cancel(this.#resizeFrame)
    this.#resizeFrame = schedule(() => {
      this.#resizeFrame = null
      this.#map?.resize()
    })
  }

  map() {
    return this.#map
  }

  destroy() {
    this.#destroyed = true
    this.#resizeObserver?.disconnect()
    this.#resizeObserver = null
    if (this.#resizeFrame !== null) {
      const cancel = this.#options.cancelFrame ?? (id => cancelAnimationFrame(id))
      cancel(this.#resizeFrame)
      this.#resizeFrame = null
    }
    if (this.#map) {
      this.#map.off('load', this.#handleLoad)
      this.#map.off('style.load', this.#handleStyleLoad)
      this.#map.remove()
      this.#map = null
    }
  }

  readonly #handleLoad = () => { void this.#notifyReady('load') }
  readonly #handleStyleLoad = () => { void this.#notifyReady('style.load') }

  async #notifyReady(reason: 'load' | 'style.load') {
    if (!this.#map || this.#destroyed) return
    for (const handler of this.#readyHandlers) await handler(this.#map, reason)
  }
}
