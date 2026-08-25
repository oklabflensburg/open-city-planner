import { describe, expect, it } from 'vitest'
import { allowedResource, attributionFromStyle, cameraForBounds, styleWithHighlight, validateStyle } from './rendering.mjs'
import { validPayload } from './validation.mjs'

describe('native map preview rendering helpers', () => {
  it('fits a bbox with a finite zoom and geographic center', () => {
    const camera = cameraForBounds([9.42, 54.77, 9.45, 54.80], 640, 360)
    expect(camera.center[0]).toBeCloseTo(9.435)
    expect(camera.center[1]).toBeGreaterThan(54.77)
    expect(camera.center[1]).toBeLessThan(54.80)
    expect(camera.zoom).toBeGreaterThan(10)
    expect(camera.zoom).toBeLessThanOrEqual(18)
  })

  it('adds a category-colored highlight without mutating the style', () => {
    const style = { version: 8, sources: {}, layers: [] }
    const result = styleWithHighlight(style, { geometry: { type: 'Polygon', coordinates: [[[9, 54], [10, 54], [10, 55], [9, 54]]] }, category: 'food', featureKind: 'polygon' })
    expect(style.layers).toHaveLength(0)
    expect(result.layers).toHaveLength(2)
    expect(result.layers[0].paint['fill-color']).toBe('#d85f67')
  })

  it('accepts only the release VersaTiles resources', () => {
    expect(allowedResource('https://tiles.versatiles.org/tiles/osm/12/1/2')).toBe(true)
    expect(allowedResource('https://tiles.versatiles.org/assets/glyphs/Noto/0-255.pbf')).toBe(true)
    expect(allowedResource('https://example.org/tiles/osm/12/1/2')).toBe(false)
    expect(allowedResource('file:///etc/passwd')).toBe(false)
    expect(allowedResource('https://user:password@tiles.versatiles.org/tiles/osm/1/2/3')).toBe(false)
  })

  it('validates the trusted style contract and derives attribution', () => {
    const style = {
      version: 8,
      glyphs: 'https://tiles.versatiles.org/assets/glyphs/{fontstack}/{range}.pbf',
      sources: {
        'versatiles-shortbread': {
          type: 'vector',
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          tiles: ['https://tiles.versatiles.org/tiles/osm/{z}/{x}/{y}']
        }
      },
      layers: []
    }
    expect(validateStyle(style)).toBe(style)
    expect(attributionFromStyle(style)).toBe('© OpenStreetMap contributors')
    expect(() => validateStyle({ ...style, glyphs: 'file:///etc/passwd' })).toThrow(/glyph URL/)
  })

  it('rejects URL injection and malformed render payloads', () => {
    const payload = {
      geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]] },
      bbox: [9.42, 54.77, 9.45, 54.80],
      width: 800,
      height: 450,
      featureKind: 'polygon',
      category: 'food'
    }
    expect(validPayload(payload)).toBe(true)
    expect(validPayload({ ...payload, styleUrl: 'file:///etc/passwd' })).toBe(false)
    expect(validPayload({ ...payload, bbox: [9.45, 54.77, 9.42, 54.80] })).toBe(false)
    expect(validPayload({ ...payload, width: 801 })).toBe(false)
  })

  it('accepts the 1200 by 630 social-card size', () => {
    expect(validPayload({
      geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]] },
      bbox: [9.42, 54.77, 9.45, 54.80],
      width: 1200,
      height: 630,
      featureKind: 'area',
      category: null
    })).toBe(true)
  })
})
