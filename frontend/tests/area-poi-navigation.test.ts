import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useOsmViewportStore } from '../app/stores/osmViewport'
import { fallbackIndustryColor, getIndustryColor } from '../app/utils/industries'
import { areaPoiMapLink, getPoiCategoryLabel, isPoiCategoryToken, withoutPoiQuery } from '../app/utils/poiCategories'

describe('Gebietsfarben und Orte', () => {
  it('uses deterministic central industry colors and a neutral fallback', () => {
    expect(getIndustryColor('gastronomy')).toBe(getIndustryColor('gastronomy'))
    expect(getIndustryColor('unbekannt')).toBe(fallbackIndustryColor)
    expect(getIndustryColor('gastronomy')).toMatch(/^#[\da-f]{6}$/i)
  })

  it('localizes concrete categories produced by area analytics', () => {
    expect(getPoiCategoryLabel('restaurant')).toBe('Restaurants')
    expect(getPoiCategoryLabel('cafe')).toBe('Cafés')
    expect(getPoiCategoryLabel('supermarket')).toBe('Supermärkte')
    expect(getPoiCategoryLabel('fast_food')).toBe('Schnellrestaurants')
    expect(getPoiCategoryLabel('social_facility')).toBe('Social facility')
  })

  it('builds a shareable map link and rejects unsafe category tokens', () => {
    expect(areaPoiMapLink('altstadt-15630273', 'restaurant')).toEqual({
      path: '/karte', query: { gebiet: 'altstadt-15630273', poi: 'restaurant' }
    })
    expect(isPoiCategoryToken('restaurant')).toBe(true)
    expect(isPoiCategoryToken('drop table')).toBe(false)
  })

  it('removes only the place filter from a map query', () => {
    expect(withoutPoiQuery({ area: 'altstadt-15630273', poi: 'restaurant', zoom: '16' })).toEqual({
      area: 'altstadt-15630273', zoom: '16'
    })
  })
})

describe('Gebiets- und Ortsfilter im OSM-Viewport', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('passes the exact area and place category to the existing viewport endpoint', () => {
    const store = useOsmViewportStore()
    store.setAreaPoiFilter('altstadt-15630273', 'restaurant')

    const query = new URLSearchParams(store.viewportRequestKey(
      { west: 9.42, south: 54.78, east: 9.44, north: 54.80 },
      16
    ))
    expect(query.get('analysis_area')).toBe('altstadt-15630273')
    expect(query.get('poi_category')).toBe('restaurant')
    expect(query.get('osm_categories')).toContain('gastronomy')
    expect(query.get('sources')).toBe('OSM')
    expect(store.showAreas).toBe(false)
  })

  it('removes only the place context while restoring the normal OSM display', () => {
    const store = useOsmViewportStore()
    store.setAreaPoiFilter('altstadt-15630273', 'restaurant')
    store.clearAreaPoiFilter()

    expect(store.areaPoiFilter).toBeNull()
    expect(store.showAreas).toBe(true)
    expect(store.showPois).toBe(true)
  })
})
