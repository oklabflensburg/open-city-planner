import type { MapSelectionPresentation, SelectedMapFeature, SelectionManagerApi } from '#frontend-module-sdk'
import { MapRuntimeError } from './errors'

export interface SelectionManagerOptions {
  readonly onSelect?: (selection: SelectedMapFeature) => void
  readonly onReveal?: (selection: SelectedMapFeature) => void
}

export class SelectionManager implements SelectionManagerApi {
  #selection: SelectedMapFeature | null = null
  readonly #presentations = new Map<string, MapSelectionPresentation>()
  readonly #listeners = new Set<(selection: SelectedMapFeature | null) => void>()

  constructor(private readonly options: SelectionManagerOptions = {}) {}

  current() {
    return this.#selection
  }

  registerPresentation(presentation: MapSelectionPresentation) {
    if (this.#presentations.has(presentation.id)) throw new MapRuntimeError(`Selection presentation "${presentation.id}" is already registered.`)
    this.#presentations.set(presentation.id, presentation)
    return () => this.unregisterPresentation(presentation.id)
  }

  unregisterPresentation(id: string) {
    const presentation = this.#presentations.get(id)
    presentation?.clear?.()
    this.#presentations.delete(id)
  }

  async select(selection: SelectedMapFeature) {
    this.#selection = Object.freeze({ ...selection })
    this.options.onSelect?.(this.#selection)
    this.#emit()
    const presentation = [...this.#presentations.values()]
      .filter(candidate => candidate.canPresent(selection))
      .sort((left, right) => (left.priority ?? 100) - (right.priority ?? 100) || left.id.localeCompare(right.id, 'en'))[0]
    await presentation?.present(selection)
  }

  reveal() {
    if (this.#selection) this.options.onReveal?.(this.#selection)
  }

  clear() {
    this.#selection = null
    for (const presentation of this.#presentations.values()) presentation.clear?.()
    this.#emit()
  }

  subscribe(listener: (selection: SelectedMapFeature | null) => void) {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  #emit() {
    for (const listener of this.#listeners) listener(this.#selection)
  }

  destroy() {
    this.clear()
    this.#listeners.clear()
    this.#presentations.clear()
  }
}
