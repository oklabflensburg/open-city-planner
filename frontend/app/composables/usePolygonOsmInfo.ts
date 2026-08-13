import type { PolygonOsmInfo } from '~/types/osm'

type PolygonReference = { id: string, slug: string, updatedAt: string }

const cache = new Map<string, PolygonOsmInfo>()
const pending = new Map<string, Promise<PolygonOsmInfo>>()

export function usePolygonOsmInfo() {
  const data = ref<PolygonOsmInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let currentRequest = 0
  let lastReference: PolygonReference | null = null

  async function loadBySlug(reference: PolygonReference, force = false) {
    lastReference = reference
    const requestNumber = ++currentRequest
    const key = `${reference.id}:${reference.updatedAt}`
    loading.value = true
    error.value = null
    if (!force && cache.has(key)) {
      data.value = cache.get(key) || null
      loading.value = false
      return data.value
    }
    try {
      let request = pending.get(key)
      if (!request) {
        request = usePolygonApi().osmBySlug(reference.slug)
        pending.set(key, request)
        void request.finally(() => pending.delete(key)).catch(() => undefined)
      }
      const result = await request
      cache.set(key, result)
      for (const cachedKey of cache.keys()) {
        if (cachedKey.startsWith(`${reference.id}:`) && cachedKey !== key) cache.delete(cachedKey)
      }
      if (requestNumber === currentRequest) data.value = result
      return result
    } catch (cause) {
      if (requestNumber === currentRequest) {
        data.value = null
        error.value = cause instanceof Error ? cause.message : 'OpenStreetMap-Daten konnten nicht geladen werden.'
      }
      return null
    } finally {
      if (requestNumber === currentRequest) loading.value = false
    }
  }

  async function retry() {
    return lastReference ? await loadBySlug(lastReference, true) : null
  }

  function clear() {
    currentRequest += 1
    lastReference = null
    data.value = null
    loading.value = false
    error.value = null
  }

  return { data, loading, error, loadBySlug, retry, clear }
}
