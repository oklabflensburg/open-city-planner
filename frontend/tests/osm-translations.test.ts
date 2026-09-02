import { describe, expect, it } from 'vitest'
import {
  formatOsmCategory,
  formatOsmTag,
  localizedOsmName,
  translateOsmKey,
  translateOsmValue
} from '~/utils/osmTranslations'

describe('central OSM presentation translations', () => {
  it.each([
    ['amenity', 'place_of_worship', 'Kategorie', 'Andachtsstätte'],
    ['building', 'cathedral', 'Gebäude', 'Kathedrale'],
    ['religion', 'christian', 'Religion', 'Christentum'],
    ['denomination', 'protestant', 'Konfession', 'Evangelisch'],
    ['amenity', 'restaurant', 'Kategorie', 'Restaurant'],
    ['wheelchair', 'yes', 'Barrierefreiheit', 'Ja'],
    ['access', 'private', 'Zugang', 'Privat']
  ])('formats %s=%s in German', (key, value, label, translated) => {
    expect(formatOsmTag(key, value)).toEqual({ label, value: translated })
  })

  it('uses the specific worship building as category', () => {
    const tags = { amenity: 'place_of_worship', building: 'church', religion: 'christian' }
    expect(formatOsmTag('amenity', tags.amenity, tags)).toEqual({ label: 'Kategorie', value: 'Kirche' })
    expect(formatOsmCategory(tags)).toEqual({ label: 'Kategorie', value: 'Kirche' })
  })

  it('falls back to readable unknown keys and values', () => {
    expect(translateOsmKey('foo_bar')).toBe('Foo bar')
    expect(translateOsmValue('amenity', 'social_facility')).toBe('Social facility')
    expect(formatOsmTag('foo_bar', 'baz_qux')).toEqual({ label: 'Foo bar', value: 'Baz qux' })
  })

  it('handles empty and absent values without throwing', () => {
    expect(formatOsmTag('amenity', '')).toBeNull()
    expect(formatOsmTag('amenity', null)).toBeNull()
    expect(formatOsmTag('amenity', undefined)).toBeNull()
  })

  it('prefers the German name and preserves names and identifiers verbatim', () => {
    const tags = { name: 'Sankt Nikolai', 'name:de': 'St. Nikolai' }
    expect(localizedOsmName(tags)).toBe('St. Nikolai')
    expect(translateOsmValue('name', 'Mürwik & Sønderborg')).toBe('Mürwik & Sønderborg')
    expect(translateOsmValue('operator', 'Stadt Flensburg')).toBe('Stadt Flensburg')
    expect(translateOsmValue('wikipedia', 'de:Lutherpark (Flensburg)')).toBe('de:Lutherpark (Flensburg)')
  })

  it('does not modify URLs or contact values', () => {
    const url = 'https://example.org/a_path?q=foo_bar'
    expect(translateOsmValue('website', url)).toBe(url)
    expect(translateOsmValue('email', 'info_test@example.org')).toBe('info_test@example.org')
    expect(translateOsmValue('phone', '+49 461 123')).toBe('+49 461 123')
  })
})
