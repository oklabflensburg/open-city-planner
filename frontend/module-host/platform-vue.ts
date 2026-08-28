import { computed } from 'vue'
import type {
  MapFilterPort,
  MapSelectionPort,
  MapSelectionReference,
  MapStylePort,
  ModuleHttpClient,
  ModuleSessionPort
} from './platform-contract.ts'
import { loadMapStyle } from '../app/config/mapStyles.ts'
import { gisFilterQuery } from '../app/utils/gisFilters.ts'

export function useModuleHttp(): ModuleHttpClient {
  return useApi()
}

export function useModuleSession(): ModuleSessionPort {
  const auth = useAuthStore()
  return { authenticated: computed(() => auth.authenticated) }
}

export function useMapFilterPort(): MapFilterPort {
  const filters = useFilterStore()
  return {
    toQuery: () => gisFilterQuery(filters.filterState)
  }
}

export function useMapSelectionPort(): MapSelectionPort {
  const mapStore = useMapStore()
  const selection = useMapSelection()
  const selected = computed<MapSelectionReference | null>(() => {
    const current = mapStore.selectedMapEntity
    if (!current) return null
    if (current.type === 'osm') {
      const properties = current.feature.properties
      return { type: current.type, id: `${properties.osm_type}/${properties.osm_id}` }
    }
    return { type: current.type, id: current.id }
  })

  return {
    selected,
    clear: selection.clearSelection
  }
}

export function useMapStylePort(): MapStylePort {
  const config = useRuntimeConfig()
  return {
    load: () => loadMapStyle(String(config.public.mapStyleUrl || ''))
  }
}
