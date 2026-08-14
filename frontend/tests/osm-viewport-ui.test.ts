import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('dynamic OSM viewport layer', () => {
  it('loads initial and moved viewports from MapLibre bounds', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('refreshOsmViewportForCurrentMap({ force: true })')
    expect(map).toContain("instance.on('moveend'")
    expect(map).not.toContain("instance.on('zoomend'")
    expect(map).toContain('instance.getBounds()')
  })

  it('debounces, aborts and sequences requests so the latest viewport wins', () => {
    const store = appFile('stores/osmViewport.ts')
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('delay = 220')
    expect(store).toContain('new AbortController()')
    expect(store).toContain('this.controller?.abort()')
    expect(store).toContain('generation === this.generation')
    expect(store).toContain('lastRequestKey')
  })

  it('restores matching cached data into recreated sources before refreshing', () => {
    const map = appFile('components/map/MapCanvas.vue')
    const store = appFile('stores/osmViewport.ts')
    expect(map).toContain('osmStore.hasCacheFor(viewport, zoom)')
    expect(map).toContain('updateOsmSources(osmStore.data)')
    expect(store).toContain('dataRequestKey')
    expect(store).toContain("this.lastRequestKey = ''")
    expect(store).toContain('this.loading = false')
  })

  it('recreates missing custom sources and layers after a style reload', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain("instance.on('style.load'")
    expect(map).toContain("if (!instance.getSource('osm-pois'))")
    expect(map).toContain("if (!instance.getSource('osm-polygons'))")
    expect(map).toContain("if (!instance.getLayer('osm-poi-circle'))")
    expect(map).toContain("if (!instance.getLayer('osm-polygons-fill'))")
  })

  it('restores the saved map view and resizes before reading bounds', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('center: mapStore.center')
    expect(map).toContain('zoom: mapStore.zoom')
    expect(map).toContain('bearing: mapStore.bearing')
    expect(map.indexOf('instance.resize()')).toBeLessThan(map.indexOf('const bounds = instance.getBounds()'))
  })

  it('creates layers once and updates long-lived GeoJSON sources with setData', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain("instance.addSource('osm-pois'")
    expect(map).toContain("instance.addSource('osm-polygons'")
    expect(map).toContain('?.setData(points)')
    expect(map).toContain('?.setData(polygons)')
  })

  it('clusters points and zooms into a tapped cluster', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('clusterMaxZoom: 14')
    expect(map).toContain("id: 'osm-clusters'")
    expect(map).toContain('getClusterExpansionZoom')
  })

  it('gives Stadtplanner polygons click priority and selects OSM points or polygons', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain("layers: ['overview-polygons-fill', 'osm-clusters', 'osm-poi-hitbox', 'osm-polygons-fill']")
    expect(map.indexOf("feature.layer.id === 'overview-polygons-fill'")).toBeLessThan(map.indexOf("feature.layer.id === 'osm-clusters'"))
    expect(map).toContain('mapSelection.selectOsm(feature)')
  })

  it('loads normalized details only after feature selection', () => {
    const store = appFile('stores/osmViewport.ts')
    const preview = appFile('components/osm/OsmFeatureSidebar.vue')
    expect(store).toContain('async select(feature: OsmViewportFeature)')
    expect(store).toContain('`/osm/features/${feature.properties.osm_type}/${feature.properties.osm_id}`')
    expect(preview).toContain('detailLoading')
    expect(preview).toContain('Auf OpenStreetMap ansehen')
  })

  it('offers OSM controls in the shared filter sheet', () => {
    const sidebar = appFile('components/layout/LeftSidebar.vue')
    const filter = appFile('components/filters/OsmFeatureFilter.vue')
    expect(sidebar).toContain('<OsmFeatureFilter')
    expect(filter).toContain('POIs anzeigen')
    expect(filter).toContain('Flächenobjekte anzeigen')
    expect(filter).toContain('Gebäude ab Zoom 17')
    expect(filter).toContain('osm.toggleCategory')
  })

  it('shows viewport counts, truncation and local OSM data date', () => {
    const summary = appFile('components/analysis/ViewportOsmSummary.vue')
    expect(summary).toContain('Aktueller Kartenausschnitt')
    expect(summary).toContain('meta.summary')
    expect(summary).toContain('meta.truncated')
    expect(summary).toContain('meta.osm_data_updated_at')
  })
})
