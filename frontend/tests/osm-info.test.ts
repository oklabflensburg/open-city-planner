import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePolygonOsmInfo } from '~/composables/usePolygonOsmInfo'
import { osmCategoryLabel } from '~/utils/osm'

const first = {
  polygon_id: 'a', polygon_slug: 'a', source: 'local' as const,
  matches: [{ osm_id: 1, osm_type: 'node' as const, shop: 'clothes', tags: {} }],
  primary_match: { osm_id: 1, osm_type: 'node' as const, shop: 'clothes', tags: {} }
}

describe('polygon OSM info', () => {
  beforeEach(() => {
    vi.stubGlobal('ref', ref)
  })

  it('maps known and unknown categories without exposing raw key=value tags', () => {
    expect(osmCategoryLabel(first.matches[0])).toBe('Mode / Bekleidung')
    expect(osmCategoryLabel({ ...first.matches[0], shop: 'charity' })).toBe('Sozialkaufhaus')
    expect(osmCategoryLabel({ ...first.matches[0], shop: 'musical_instrument' })).toBe('Musical instrument')
  })

  it('deduplicates identical requests and exposes the primary match', async () => {
    const osmBySlug = vi.fn().mockResolvedValue(first)
    vi.stubGlobal('usePolygonApi', () => ({ osmBySlug }))
    const a = usePolygonOsmInfo()
    const b = usePolygonOsmInfo()

    await Promise.all([
      a.loadBySlug({ id: 'a', slug: 'a', updatedAt: '1' }),
      b.loadBySlug({ id: 'a', slug: 'a', updatedAt: '1' })
    ])

    expect(osmBySlug).toHaveBeenCalledTimes(1)
    expect(a.data.value?.primary_match?.osm_id).toBe(1)
    expect(a.loading.value).toBe(false)
  })

  it('does not let an older polygon response overwrite the current polygon', async () => {
    let resolveA!: (value: typeof first) => void
    const osmBySlug = vi.fn((slug: string) => slug === 'a'
      ? new Promise<typeof first>(resolve => { resolveA = resolve })
      : Promise.resolve({ ...first, polygon_id: 'b', polygon_slug: 'b' }))
    vi.stubGlobal('usePolygonApi', () => ({ osmBySlug }))
    const state = usePolygonOsmInfo()

    const oldRequest = state.loadBySlug({ id: 'race-a', slug: 'a', updatedAt: '1' })
    await state.loadBySlug({ id: 'race-b', slug: 'b', updatedAt: '1' })
    resolveA(first)
    await oldRequest

    expect(state.data.value?.polygon_id).toBe('b')
  })

  it('exposes errors and supports retry', async () => {
    const osmBySlug = vi.fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(first)
    vi.stubGlobal('usePolygonApi', () => ({ osmBySlug }))
    const state = usePolygonOsmInfo()

    await state.loadBySlug({ id: 'retry', slug: 'retry', updatedAt: '1' })
    expect(state.error.value).toBe('offline')
    await state.retry()
    expect(state.data.value?.matches).toHaveLength(1)
    expect(state.error.value).toBeNull()
  })
})
