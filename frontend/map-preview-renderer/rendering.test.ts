import { describe, expect, it } from 'vitest'
import { cameraForBounds, styleWithHighlight } from './rendering.mjs'

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
})
