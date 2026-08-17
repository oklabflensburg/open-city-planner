import { GIS_FILTER_QUERY_KEYS, gisFiltersFromQuery, gisFilterStateKey, gisFilterUrlQuery } from '~/utils/gisFilters'

export default defineNuxtPlugin(() => {
  const route = useRoute()
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
    if (window.location.pathname !== '/') return
    const next = gisFiltersFromQuery(locationQuery())
    const nextKey = gisFilterStateKey(next)
    if (nextKey !== filters.stateKey) {
      applyingLocation = true
      filters.applyFilters(next)
      await nextTick()
      applyingLocation = false
    }
    ready = true
  }

  void applyLocation()
  window.addEventListener('popstate', applyLocation)

  watch(() => route.path, () => {
    void applyLocation()
  })

  watch(() => filters.stateKey, () => {
    if (!ready || applyingLocation || window.location.pathname !== '/') return
    clearTimeout(historyTimer)
    historyTimer = setTimeout(() => {
      const url = new URL(window.location.href)
      for (const key of GIS_FILTER_QUERY_KEYS) url.searchParams.delete(key)
      for (const [key, value] of gisFilterUrlQuery(filters.filterState)) url.searchParams.set(key, value)
      window.history.pushState({ ...window.history.state }, '', url)
    }, 200)
  })
})
