import {
  GIS_FILTER_QUERY_KEYS,
  gisFiltersFromQuery,
  gisFilterStateKey,
  gisFilterUrlQuery
} from '~/utils/gisFilters'
import { poiFromQuery, withPoiQuery } from '~/utils/poiCategories'

/** Keeps the GIS filter state in the URL only while the map application is mounted. */
export function useGisFilterHistory() {
  const filters = useFilterStore()
  const osm = useOsmViewportStore()
  const route = useRoute()
  let applyingLocation = false
  let ready = false
  let historyTimer: ReturnType<typeof setTimeout> | undefined

  // Apply the route during setup so SSR and hydration start from the same
  // canonical map-filter state.
  osm.setPoi(poiFromQuery(route.query.poi))

  function locationQuery(): Record<string, string | string[]> {
    const params = new URLSearchParams(window.location.search)
    return Object.fromEntries(GIS_FILTER_QUERY_KEYS.map((key) => {
      const values = params.getAll(key)
      return [key, values.length > 1 ? values : values[0] ?? '']
    }))
  }

  async function applyLocation() {
    const next = gisFiltersFromQuery(locationQuery())
    const nextPoi = poiFromQuery(new URLSearchParams(window.location.search).get('poi'))
    const nextKey = gisFilterStateKey(next)
    if (nextKey !== filters.stateKey || nextPoi !== osm.poi) {
      applyingLocation = true
      filters.applyFilters(next)
      osm.setPoi(nextPoi)
      await nextTick()
      applyingLocation = false
    }
    canonicalizeLocation(next, nextPoi)
    ready = true
  }

  function canonicalizeLocation(next: ReturnType<typeof gisFiltersFromQuery>, poi: string | null) {
    const current = new URL(window.location.href)
    const previous = current.search
    const url = withPoiQuery(current, poi)
    for (const key of GIS_FILTER_QUERY_KEYS) url.searchParams.delete(key)
    for (const [key, value] of gisFilterUrlQuery(next)) url.searchParams.set(key, value)
    if (url.search !== previous) window.history.replaceState({ ...window.history.state }, '', url)
  }

  onMounted(() => {
    void applyLocation()
    window.addEventListener('popstate', applyLocation)
  })

  watch(() => [filters.stateKey, osm.poi], () => {
    if (!ready || applyingLocation) return
    clearTimeout(historyTimer)
    historyTimer = setTimeout(() => {
      const url = withPoiQuery(new URL(window.location.href), osm.poi)
      for (const key of GIS_FILTER_QUERY_KEYS) url.searchParams.delete(key)
      for (const [key, value] of gisFilterUrlQuery(filters.filterState)) {
        url.searchParams.set(key, value)
      }
      window.history.pushState({ ...window.history.state }, '', url)
    }, 200)
  })

  watch(() => route.fullPath, () => {
    if (import.meta.client) void applyLocation()
  })

  onBeforeUnmount(() => {
    clearTimeout(historyTimer)
    window.removeEventListener('popstate', applyLocation)
  })
}
