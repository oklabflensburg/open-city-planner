import { afterEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import {
  useMapFilterPort,
  useMapSelectionPort,
  useMapStylePort,
  useModuleHttp
} from '../module-host/platform-vue'

afterEach(() => vi.unstubAllGlobals())

describe('public frontend platform ports', () => {
  it('exposes the existing authenticated HTTP client without another runtime', () => {
    const client = { request: vi.fn() }
    vi.stubGlobal('useApi', () => client)
    expect(useModuleHttp()).toBe(client)
  })

  it('projects active map filters without exposing the host store', () => {
    vi.stubGlobal('useFilterStore', () => ({
      filterState: {
        sizes: [],
        floors: [],
        categories: [],
        statuses: [],
        businessStructures: [],
        sources: []
      }
    }))
    const first = useMapFilterPort().toQuery()
    const second = useMapFilterPort().toQuery()
    expect(first).not.toBe(second)
    expect(first.get('area_sizes')).toBe('NONE')
    expect(first.get('sources')).toBe('NONE')
  })

  it('reads, validates, reveals and clears generic map selections', () => {
    const clearSelection = vi.fn()
    const mapStore = reactive({
      selectedMapEntity: null as null | { type: string, id: string },
      openGisPanel: vi.fn()
    })
    vi.stubGlobal('useMapStore', () => mapStore)
    vi.stubGlobal('useMapSelection', () => ({ clearSelection }))
    const port = useMapSelectionPort()

    expect(port.selected.value).toBeNull()
    port.select({ type: 'example-item', id: '42' }, { reveal: true })
    expect(port.selected.value).toEqual({ type: 'example-item', id: '42' })
    expect(mapStore.openGisPanel).toHaveBeenCalledWith('selection')
    expect(() => port.select({ type: '', id: '42' })).toThrow(/non-empty type and ID/)
    port.clear()
    expect(clearSelection).toHaveBeenCalledOnce()
  })

  it('loads the configured map style only when requested', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 8, sources: {}, layers: [] })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { mapStyleUrl: '/custom-style.json' } }))
    const port = useMapStylePort()
    expect(fetchMock).not.toHaveBeenCalled()
    await expect(port.load()).resolves.toMatchObject({ version: 8 })
    expect(fetchMock).toHaveBeenCalledWith('/custom-style.json', { headers: { Accept: 'application/json' } })
  })
})
