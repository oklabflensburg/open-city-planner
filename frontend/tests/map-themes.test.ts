import { describe, expect, it } from 'vitest'
import {
  businessColors,
  occupancyColors,
  sizeColors,
  thematicColor,
  thematicColorExpression
} from '~/utils/mapThemes'

describe('zentrale Kartenfarben', () => {
  it('verwendet dieselben Statusfarben für Einzelwerte und MapLibre-Ausdrücke', () => {
    expect(occupancyColors).toEqual({
      OCCUPIED: '#10b981',
      VACANT: '#f43f5e',
      UNKNOWN: '#94a3b8'
    })
    expect(thematicColor('occupancy', { occupancy_status: 'VACANT' })).toBe('#f43f5e')
    expect(thematicColorExpression('occupancy')).toEqual([
      'match', ['get', 'occupancy_status'],
      'OCCUPIED', '#10b981',
      'VACANT', '#f43f5e',
      '#94a3b8'
    ])
  })

  it('liefert auch für Größe und Betriebsform zentrale Farben', () => {
    expect(thematicColor('size', { size: 'XL' })).toBe(sizeColors.XL)
    expect(thematicColor('business', { business_structure: 'CHAIN' })).toBe(businessColors.CHAIN)
  })
})
