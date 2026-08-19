import {
  GIS_FILTER_QUERY_KEYS,
  gisFiltersFromQuery,
  gisFilterStateKey,
  gisFilterUrlQuery
} from '~/utils/gisFilters'

/** Keeps the GIS filter state in the URL only while the map application is mounted. */
export function useGisFilterHistory() {
  const filters = useFilterStore()
  let applyingLocation = false
  let ready = false
  let historyTimer: ReturnType<typeof setTimeout> | undefined

  function locationQuery(): Record<string, string | string[]> {
    const params = new URLSearchParams(window.location.search)
    return Object.fromEntries(GIS_FILTER_QUERY_KEYS.map((key) => {
      const values = params.getAll(key)
      return [key, values.length > 1 ? values : values[0] ?? '']
    }))
  }

  async function applyLocation() {
    const next = gisFiltersFromQuery(locationQuery())
    const nextKey = gisFilterStateKey(next)
    if (nextKey !== filters.stateKey) {
      applyingLocation = true
      filters.applyFilters(next)
      await nextTick()
      applyingLocation = false
    }
    canonicalizeLocation(next)
    ready = true
  }

  function canonicalizeLocation(next: ReturnType<typeof gisFiltersFromQuery>) {
    const url = new URL(window.location.href)
    const previous = url.search
    for (const key of GIS_FILTER_QUERY_KEYS) url.searchParams.delete(key)
    for (const [key, value] of gisFilterUrlQuery(next)) url.searchParams.set(key, value)
    if (url.search !== previous) window.history.replaceState({ ...window.history.state }, '', url)
  }

  onMounted(() => {
    void applyLocation()
    window.addEventListener('popstate', applyLocation)
  })

  watch(() => filters.stateKey, () => {
    if (!ready || applyingLocation) return
    clearTimeout(historyTimer)
    historyTimer = setTimeout(() => {
      const url = new URL(window.location.href)
      for (const key of GIS_FILTER_QUERY_KEYS) url.searchParams.delete(key)
      for (const [key, value] of gisFilterUrlQuery(filters.filterState)) {
        url.searchParams.set(key, value)
      }
      window.history.pushState({ ...window.history.state }, '', url)
    }, 200)
  })

  onBeforeUnmount(() => {
    clearTimeout(historyTimer)
    window.removeEventListener('popstate', applyLocation)
  })
}
