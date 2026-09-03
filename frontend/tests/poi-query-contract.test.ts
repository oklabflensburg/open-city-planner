import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { getPoiCategoryLabel, poiFromQuery, withPoiQuery } from '~/utils/poiCategories'

describe('public POI query contract', () => {
  it('restores a safe category from a deep link and rejects ambiguous values', () => {
    expect(poiFromQuery('cafe')).toBe('cafe')
    expect(poiFromQuery(['cafe', 'restaurant'])).toBeNull()
    expect(poiFromQuery('drop table')).toBeNull()
  })

  it('writes, changes and clears only the canonical POI query parameter', () => {
    const original = new URL('https://stadtplaner.example/karte?gebiet=innenstadt-test&zoom=16')
    const cafe = withPoiQuery(original, 'cafe')
    expect(cafe.searchParams.get('poi')).toBe('cafe')
    expect(cafe.searchParams.get('gebiet')).toBe('innenstadt-test')

    const restaurant = withPoiQuery(cafe, 'restaurant')
    expect(restaurant.searchParams.get('poi')).toBe('restaurant')

    const cleared = withPoiQuery(restaurant, null)
    expect(cleared.searchParams.has('poi')).toBe(false)
    expect(cleared.searchParams.get('zoom')).toBe('16')
  })

  it('uses the same value after serializing and reloading a deep link', () => {
    const written = withPoiQuery(new URL('https://stadtplaner.example/karte'), 'cafe')
    expect(poiFromQuery(new URL(written.href).searchParams.get('poi'))).toBe('cafe')
    expect(getPoiCategoryLabel('cafe')).toBe('Cafés')
  })

  it('keeps the retired provider-specific query key out of frontend runtime sources', () => {
    const retiredKey = ['osm', 'kategorie'].join('_')
    const runtimeFiles = [
      'app',
      'module-host',
      'server'
    ]
    const candidates = runtimeFiles.flatMap(directory => sourceFiles(resolve(import.meta.dirname, '..', directory)))
    const violations = candidates.filter(path => readFileSync(path, 'utf8').includes(retiredKey))
    expect(violations).toEqual([])
  })
})

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(?:ts|vue)$/.test(entry.name) ? [path] : []
  })
}
