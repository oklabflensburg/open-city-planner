import type { DrawAdapter, DrawManagerApi } from '#frontend-module-sdk'
import type { TerraDraw } from 'terra-draw'
import { MapRuntimeError } from './errors'

export class DrawManager implements DrawManagerApi {
  #adapter: DrawAdapter | null = null

  initialize(factory: () => DrawAdapter) {
    if (this.#adapter) throw new MapRuntimeError('DrawManager already owns an active draw adapter.')
    this.#adapter = factory()
    return this.#adapter
  }

  startMode(mode: string) {
    if (!this.#adapter) throw new MapRuntimeError('DrawManager has not been initialized.')
    this.#adapter.start()
    this.#adapter.setMode(mode)
  }

  stop() {
    this.#adapter?.stop()
  }

  clear() {
    this.#adapter?.clear()
  }

  destroy() {
    this.#adapter?.destroy()
    this.#adapter = null
  }
}

/** Keeps Terra Draw behind the stable DrawAdapter used by the public MapContext. */
export function createTerraDrawAdapter(draw: TerraDraw): DrawAdapter {
  const clear = () => {
    const ids = draw.getSnapshot().map(feature => feature.id).filter((id): id is string | number => id != null)
    if (ids.length) draw.removeFeatures(ids)
  }
  return {
    start: () => draw.start(),
    stop: () => draw.stop(),
    setMode: mode => draw.setMode(mode),
    clear,
    destroy: () => {
      clear()
      draw.stop()
    }
  }
}
