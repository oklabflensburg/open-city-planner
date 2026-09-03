import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { expandOsmBounds, useOsmViewportStore } from '~/stores/osmViewport'
import type { OsmViewportResult } from '~/types/osm'

const bounds = { west: 9.43, south: 54.78, east: 9.44, north: 54.79 }
const response: OsmViewportResult = {
  type: 'FeatureCollection',
  features: [],
  meta: { count: 0, truncated: false, zoom: 16, summary: {}, canonical_summary: {}, canonical_facets: {}, business_count: 0, context_count: 0, deduplicated_linked_count: 0, osm_data_updated_at: '2026-08-14T00:00:00Z' }
}

describe('OSM viewport store lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('reuses a matching cache normally and refreshes it when forced after route return', async () => {
    const request = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useOsmViewportStore()

    await store.load(bounds, 16)
    await store.load(bounds, 16)
    expect(request).toHaveBeenCalledTimes(1)
    expect(store.hasCacheFor(bounds, 16)).toBe(true)

    await store.load(bounds, 16, { force: true })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('aborts an old route request and creates a fresh controller on re-entry', async () => {
    const signals: AbortSignal[] = []
    const request = vi.fn((_url: string, options: { signal: AbortSignal }) => {
      signals.push(options.signal)
      return new Promise<OsmViewportResult>((resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        if (signals.length > 1) resolve(response)
      })
    })
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useOsmViewportStore()

    const firstLoad = store.load(bounds, 16)
    await Promise.resolve()
    store.dispose()
    await firstLoad

    expect(signals[0]?.aborted).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.lastRequestKey).toBe('')

    await store.load(bounds, 16, { force: true })
    expect(signals[1]).not.toBe(signals[0])
    expect(signals[1]?.aborted).toBe(false)
    expect(store.data).toEqual(response)
  })

  it('retains valid cached features when a background refresh fails', async () => {
    const request = vi.fn().mockResolvedValueOnce(response).mockRejectedValueOnce(new Error('offline'))
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useOsmViewportStore()

    await store.load(bounds, 16)
    await store.load(bounds, 16, { force: true })

    expect(store.data).toEqual(response)
    expect(store.hasCacheFor(bounds, 16)).toBe(true)
    expect(store.error).toBe('offline')
  })

  it('skips network work while a moved viewport remains inside the buffered bounds', async () => {
    const request = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useOsmViewportStore()
    const buffered = expandOsmBounds(bounds)

    await store.load(buffered, 16)

    expect(store.covers(bounds, 16)).toBe(true)
    expect(store.covers({ ...bounds, east: buffered.east + 0.001 }, 16)).toBe(false)
    expect(store.covers(bounds, 17)).toBe(false)
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('drops viewport data and the LRU cache after a polygon mutation changes deduplication', async () => {
    vi.stubGlobal('useApi', () => ({ request: vi.fn().mockResolvedValue(response) }))
    const store = useOsmViewportStore()
    await store.load(bounds, 16)
    const generation = store.generation

    store.invalidateForPolygonMutation()

    expect(store.data).toBeNull()
    expect(store.viewportCache.size).toBe(0)
    expect(store.generation).toBe(generation + 1)
    expect(store.lastRequestKey).toBe('')
  })

  it('uses the semantic POI filter for viewport requests without leaking provider URL state', () => {
    const store = useOsmViewportStore()
    store.setPoi('cafe')

    const query = new URLSearchParams(store.viewportRequestKey(bounds, 16))
    expect(store.poi).toBe('cafe')
    expect(query.get('poi')).toBe('cafe')
    expect(query.get('osm_categories')).toContain('gastronomy')
    expect(query.get('sources')).toBeNull()

    store.setPoi('restaurant')
    expect(new URLSearchParams(store.viewportRequestKey(bounds, 16)).get('poi')).toBe('restaurant')
    store.clearPoi()
    expect(store.poi).toBeNull()
    expect(new URLSearchParams(store.viewportRequestKey(bounds, 16)).has('poi')).toBe(false)
  })
})
