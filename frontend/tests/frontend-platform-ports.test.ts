import { afterEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import {
  useMapFilterPort,
  useMapSelectionPort,
  useMapStylePort,
  useModuleHttp,
  useModuleSeo,
  useModuleSession
} from '../module-host/platform-vue'

afterEach(() => vi.unstubAllGlobals())

describe('public frontend platform ports', () => {
  it('delegates module metadata to the existing host SEO runtime', () => {
    const useSeoMeta = vi.fn()
    const useHead = vi.fn()
    vi.stubGlobal('useRuntimeConfig', () => ({ public: {
      siteName: 'Stadtplaner', siteUrl: 'https://example.test', siteLocale: 'de_DE', defaultOgImage: '/og.png'
    } }))
    vi.stubGlobal('useSeoMeta', useSeoMeta)
    vi.stubGlobal('useHead', useHead)
    useModuleSeo({ title: 'Modulseite', description: 'Öffentliche Beschreibung', path: '/modul' })
    expect(useSeoMeta).toHaveBeenCalledWith(expect.objectContaining({ title: 'Modulseite – Stadtplaner' }))
    expect(useHead).toHaveBeenCalledWith(expect.objectContaining({
      link: [{ rel: 'canonical', href: 'https://example.test/modul' }]
    }))
  })

  it('exposes the existing authenticated HTTP client without another runtime', () => {
    const client = { request: vi.fn() }
    vi.stubGlobal('useApi', () => client)
    expect(useModuleHttp()).toBe(client)
  })

  it('projects authentication state without exposing the host auth store', () => {
    const auth = reactive({ authenticated: false, privateUser: { email: 'private@example.org' } })
    vi.stubGlobal('useAuthStore', () => auth)
    const session = useModuleSession()
    expect(session.authenticated.value).toBe(false)
    auth.authenticated = true
    expect(session.authenticated.value).toBe(true)
    expect(session).not.toHaveProperty('privateUser')
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

  it('projects and clears host map selections without exposing private entities', () => {
    const clearSelection = vi.fn()
    const mapStore = reactive({
      runtimeSelection: null as null | {
        moduleId: string
        featureId: string
      },
      selectedMapEntity: null as null
        | { type: 'analysis-area', id: string }
        | { type: 'polygon', id: string }
        | {
          type: 'osm'
          feature: {
            properties: { osm_type: 'node' | 'way' | 'relation', osm_id: number }
            privatePayload: string
          }
        }
    })
    vi.stubGlobal('useMapStore', () => mapStore)
    vi.stubGlobal('useMapSelection', () => ({ clearSelection }))
    const port = useMapSelectionPort()

    expect(port.selected.value).toBeNull()
    mapStore.runtimeSelection = { moduleId: 'demo', featureId: 'module-1' }
    expect(port.selected.value).toEqual({ type: 'demo', id: 'module-1' })
    mapStore.runtimeSelection = null
    mapStore.selectedMapEntity = { type: 'analysis-area', id: 'area-42' }
    expect(port.selected.value).toEqual({ type: 'analysis-area', id: 'area-42' })
    mapStore.selectedMapEntity = { type: 'polygon', id: 'polygon-7' }
    expect(port.selected.value).toEqual({ type: 'polygon', id: 'polygon-7' })
    mapStore.selectedMapEntity = {
      type: 'osm',
      feature: {
        properties: { osm_type: 'node', osm_id: 123 },
        privatePayload: 'must not cross the public boundary'
      }
    }
    expect(port.selected.value).toEqual({ type: 'osm', id: 'node/123' })
    expect(port.selected.value).not.toHaveProperty('feature')
    expect(port.selected.value).not.toHaveProperty('privatePayload')
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
