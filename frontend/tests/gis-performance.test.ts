import { describe, expect, it } from 'vitest'
import { mapHostSource } from './map-host-source'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('GIS performance safeguards', () => {
  it('keeps viewport requests bounded by zoom and mobile capacity', () => {
    const store = appFile('stores/osmViewport.ts')
    expect(store).toContain("const mobile = import.meta.client && window.matchMedia('(max-width: 767px)').matches")
    expect(store).toContain('mobile ? 800 : zoom < 15 ? 800 : zoom < 17 ? 1200 : 2000')
  })

  it('retains moveend debouncing, cancellation, identical-key suppression and setData updates', () => {
    const store = appFile('stores/osmViewport.ts')
    const map = mapHostSource()
    expect(store).toContain('key === this.lastRequestKey')
    expect(store).toContain('this.controller?.abort()')
    expect(map).toContain("instance.on('moveend'")
    expect(map).toContain('scheduleOsmViewportRefresh()')
    expect(map).toContain("getSource('osm-pois')")
    expect(map).toContain('setData(points)')
    expect(map).not.toContain('osmStore.data = null')
  })

  it('keeps active pan free of reactive map updates and expensive source work', () => {
    const map = mapHostSource()
    expect(map).toContain('map.value = markRaw(instance)')
    expect(map).toContain("instance.on('moveend'")
    expect(map).not.toContain("instance.on('move',")
    expect(map).not.toContain("instance.on('render',")
    expect(map).toContain('hoverFrame = requestAnimationFrame')
    expect(map).toContain("powerPreference: 'high-performance'")
    expect(map).toContain('setFeatureState')
    expect(map).not.toContain('instance.resize()')
  })

  it('uses buffered viewport coverage and non-reactive bounded GeoJSON storage', () => {
    const store = appFile('stores/osmViewport.ts')
    const map = mapHostSource()
    expect(store).toContain('VIEWPORT_BUFFER_RATIO = 0.2')
    expect(store).toContain('VIEWPORT_CACHE_SIZE = 4')
    expect(store).toContain('containsBounds(this.loadedBounds, bounds)')
    expect(store).toContain('this.data = markRaw')
    expect(map).toContain('if (!options.force && osmStore.covers(viewport, zoom)) return')
  })

  it('renders every polygon through one bounded selection overlay without click auto-zoom', () => {
    const map = mapHostSource()
    expect(map).toContain("instance.addSource('selected-polygon-source'")
    expect(map).toContain("id: 'selected-polygon-fill'")
    expect(map).toContain("id: 'selected-polygon-halo'")
    expect(map).toContain("id: 'selected-polygon-outline'")
    expect(map).toContain("id: 'osm-selected-point-halo'")
    expect(map).toContain("source.setData({ type: 'FeatureCollection', features }")
    expect(map).toContain('function selectInteractivePolygon')
    expect(map).toContain('async function selectPolygon(id: string, fitSelection = false)')
    expect(map).toContain('if (fitSelection && bbox && map.value)')
    expect(map).not.toContain('setStyle(')
  })
})
