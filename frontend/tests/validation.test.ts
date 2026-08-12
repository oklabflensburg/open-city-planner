import { describe, expect, it } from 'vitest'
import { featureCollectionSchema, polygonGeometrySchema } from '~/utils/validation'

describe('geo validation', () => {
  it('accepts valid polygon geometry', () => {
    expect(
      polygonGeometrySchema.parse({
        type: 'Polygon',
        coordinates: [[
          [9.43, 54.78],
          [9.44, 54.78],
          [9.44, 54.79],
          [9.43, 54.78]
        ]]
      })
    ).toBeTruthy()
  })

  it('accepts feature collections', () => {
    expect(featureCollectionSchema.parse({ type: 'FeatureCollection', features: [] }).features).toEqual([])
  })
})

