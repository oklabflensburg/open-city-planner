import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  DEFAULT_MAP_STYLE_URL,
  FALLBACK_MAP_STYLE_URL,
  loadMapStyle,
  resolveMapStyleUrl
} from '../app/config/mapStyles'
import { mapHostSource } from './map-host-source'

const style = JSON.parse(readFileSync(resolve(process.cwd(), 'public/map-styles/stadtplaner-light.json'), 'utf8'))
const mapCanvas = mapHostSource()
const availableSourceLayers = new Set([
  'ocean', 'water_polygons', 'land', 'water_lines', 'dam_polygons', 'dam_lines',
  'pier_polygons', 'pier_lines', 'sites', 'street_polygons', 'streets', 'buildings',
  'bridges', 'ferries', 'boundaries', 'addresses', 'street_labels', 'public_transport',
  'place_labels', 'boundary_labels'
])

afterEach(() => vi.unstubAllGlobals())

describe('Stadtplaner Light map style', () => {
  it('is the local default and keeps explicit configuration overrides', () => {
    expect(resolveMapStyleUrl()).toBe(DEFAULT_MAP_STYLE_URL)
    expect(resolveMapStyleUrl('  https://maps.example/style.json  ')).toBe('https://maps.example/style.json')
  })

  it('uses only real Shortbread source layers and a small unique layer set', () => {
    expect(style.version).toBe(8)
    expect(style.name).toBe('Stadtplaner Light')
    expect(style.layers).toHaveLength(24)
    expect(new Set(style.layers.map((layer: { id: string }) => layer.id)).size).toBe(style.layers.length)
    for (const layer of style.layers) {
      if (layer['source-layer']) expect(availableSourceLayers.has(layer['source-layer'])).toBe(true)
    }
  })

  it('keeps detailed geometry out of low zooms and avoids duplicate commerce POIs', () => {
    expect(style.layers.find((layer: { id: string }) => layer.id === 'buildings').minzoom).toBe(15)
    expect(style.layers.find((layer: { id: string }) => layer.id === 'paths').minzoom).toBe(16)
    expect(style.layers.filter((layer: { type: string }) => layer.type === 'symbol')).toHaveLength(5)
    expect(JSON.stringify(style.layers)).not.toMatch(/restaurant|cafe|shop|supermarket/)
  })

  it('uses glyph stacks that are available from the configured VersaTiles server', () => {
    for (const layer of style.layers.filter((item: { type: string }) => item.type === 'symbol')) {
      expect(layer.layout['text-font']).toMatchObject([expect.stringMatching(/^noto_sans_/)])
    }
    expect(mapCanvas).toContain("['get', 'point_count_abbreviated'], 'text-font': ['noto_sans_regular']")
    expect(`${JSON.stringify(style)}${mapCanvas}`).not.toContain('Arial Unicode MS')
  })

  it('loads Neutrino only after the configured/local style fails', async () => {
    const fallbackStyle = { version: 8, sources: {}, layers: [] }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('', { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(fallbackStyle), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadMapStyle('/broken.json')).resolves.toEqual(fallbackStyle)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/broken.json', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, FALLBACK_MAP_STYLE_URL, expect.any(Object))
  })

  it('reports both URLs when primary and fallback fail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(loadMapStyle()).rejects.toThrow(DEFAULT_MAP_STYLE_URL)
    await expect(loadMapStyle()).rejects.toThrow(FALLBACK_MAP_STYLE_URL)
  })
})
