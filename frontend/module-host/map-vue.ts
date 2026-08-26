import { inject, readonly, type InjectionKey, type Ref } from 'vue'
import type { MapContext } from './map-contract'

export const MAP_CONTEXT_KEY: InjectionKey<Ref<MapContext | null>> = Symbol.for('open-city-planner.map-context')

export function useMapContext() {
  const context = inject(MAP_CONTEXT_KEY)
  if (!context) throw new Error('MapContext is only available inside the map host.')
  return readonly(context)
}
