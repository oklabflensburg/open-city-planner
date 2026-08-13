import { describe, expect, it } from 'vitest'
import { formatMetricIndex, formatMetricPercent } from '~/utils/metrics'
import { hasVerwaltungRole } from '~/utils/roles'

describe('city metrics UI rules', () => {
  it('formats real values with German locale and null as dash', () => {
    expect(formatMetricPercent(6.25)).toBe('6,25 %')
    expect(formatMetricPercent(null)).toBe('—')
    expect(formatMetricIndex(154.5)).toBe('154,5')
    expect(formatMetricIndex(null)).toBe('—')
  })

  it('allows management controls only for VERWALTUNG and superusers', () => {
    expect(hasVerwaltungRole({ is_superuser: false, roles: ['USER'] })).toBe(false)
    expect(hasVerwaltungRole({ is_superuser: false, roles: ['verwaltung'] })).toBe(true)
    expect(hasVerwaltungRole({ is_superuser: true, roles: [] })).toBe(true)
    expect(hasVerwaltungRole(null)).toBe(false)
  })
})
