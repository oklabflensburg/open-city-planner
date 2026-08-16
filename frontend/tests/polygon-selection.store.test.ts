import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMapStore } from '~/stores/map'
import { usePolygonStore } from '~/stores/polygon'
import type { PolygonMetrics, PolygonOverview } from '~/types/geo'

const polygon = (id: string): PolygonOverview => ({
  id,
  slug: id,
  name: `Polygon ${id}`,
  category: 'food',
  geometry: { type: 'Polygon', coordinates: [[[9, 54], [10, 54], [10, 55], [9, 54]]] },
  occupancy_status: 'UNKNOWN',
  business_structure: 'UNKNOWN',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
})
const metrics = (area_m2: number): PolygonMetrics => ({
  area_m2,
  perimeter_m: 10,
  centroid: [9, 54],
  bbox: [9, 54, 10, 55]
})
const osmInfo = (id: string) => ({ polygon_id: id, polygon_slug: id, source: 'local' as const, matches: [], primary_match: null })

describe('polygon map selection loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('shows base data immediately and requests metrics and OSM once', async () => {
    let resolveMetrics!: (value: PolygonMetrics) => void
    const metricsRequest = vi.fn(() => new Promise<PolygonMetrics>(resolve => { resolveMetrics = resolve }))
    const osmRequest = vi.fn().mockResolvedValue(osmInfo('a'))
    vi.stubGlobal('usePolygonApi', () => ({ metrics: metricsRequest, osmBySlug: osmRequest }))
    const map = useMapStore()
    const store = usePolygonStore()
    store.polygons = [polygon('a')]
    map.selectedMapEntity = { type: 'polygon', id: 'a' }

    const loading = store.loadSelection('a')

    expect(store.selectedPolygon?.name).toBe('Polygon a')
    expect(store.metricsLoading).toBe(true)
    expect(metricsRequest).toHaveBeenCalledTimes(1)
    expect(osmRequest).toHaveBeenCalledTimes(1)
    resolveMetrics(metrics(100))
    await loading
    expect(store.selectedMetrics?.area_m2).toBe(100)
  })

  it('does not let late responses from polygon A overwrite polygon B', async () => {
    let resolveA!: (value: PolygonMetrics) => void
    const metricsRequest = vi.fn((id: string) => id === 'a'
      ? new Promise<PolygonMetrics>(resolve => { resolveA = resolve })
      : Promise.resolve(metrics(200)))
    vi.stubGlobal('usePolygonApi', () => ({ metrics: metricsRequest, osmBySlug: vi.fn((slug: string) => Promise.resolve(osmInfo(slug))) }))
    const map = useMapStore()
    const store = usePolygonStore()
    store.polygons = [polygon('a'), polygon('b')]

    map.selectedMapEntity = { type: 'polygon', id: 'a' }
    const oldRequest = store.loadSelection('a')
    map.selectedMapEntity = { type: 'polygon', id: 'b' }
    await store.loadSelection('b')
    resolveA(metrics(100))
    await oldRequest

    expect(store.selectedPolygonId).toBe('b')
    expect(store.selectedMetrics?.area_m2).toBe(200)
  })

  it('keeps selection and OSM data visible when metrics fail', async () => {
    vi.stubGlobal('usePolygonApi', () => ({
      metrics: vi.fn().mockRejectedValue(new Error('metrics offline')),
      osmBySlug: vi.fn().mockResolvedValue(osmInfo('a'))
    }))
    const map = useMapStore()
    const store = usePolygonStore()
    store.polygons = [polygon('a')]
    map.selectedMapEntity = { type: 'polygon', id: 'a' }

    await store.loadSelection('a')

    expect(map.selectedMapEntity).toEqual({ type: 'polygon', id: 'a' })
    expect(store.metricsError).toBe('metrics offline')
    expect(store.selectedOsmInfo?.polygon_id).toBe('a')
  })
})
