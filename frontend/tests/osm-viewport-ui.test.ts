import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { mapHostSource } from './map-host-source'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')
const moduleFile = (path: string) => readFileSync(fileURLToPath(new URL(`../frontend-modules/analysis-areas/layer/app/${path}`, import.meta.url)), 'utf8')

describe('dynamic OSM viewport layer', () => {
  it('loads initial and moved viewports from MapLibre bounds', () => {
    const map = mapHostSource()
    expect(map).toContain('refreshOsmViewportForCurrentMap({ force: true })')
    expect(map).toContain("instance.on('moveend'")
    expect(map).not.toContain("instance.on('zoomend'")
    expect(map).toContain('instance.getBounds()')
  })

  it('debounces, aborts and sequences requests so the latest viewport wins', () => {
    const store = appFile('stores/osmViewport.ts')
    const map = mapHostSource()
    expect(map).toContain('delay = 220')
    expect(store).toContain('new AbortController()')
    expect(store).toContain('this.controller?.abort()')
    expect(store).toContain('generation === this.generation')
    expect(store).toContain('lastRequestKey')
  })

  it('uses buffered coverage and a bounded local cache before refreshing', () => {
    const map = mapHostSource()
    const store = appFile('stores/osmViewport.ts')
    expect(map).toContain('osmStore.covers(viewport, zoom)')
    expect(map).toContain('expandOsmBounds(viewport)')
    expect(store).toContain('VIEWPORT_CACHE_SIZE = 4')
    expect(store).toContain('markRaw(new Map<string, CachedViewport>())')
    expect(store).toContain('dataRequestKey')
    expect(store).toContain("this.lastRequestKey = ''")
    expect(store).toContain('this.loading = false')
  })

  it('recreates missing custom sources and layers after a style reload', () => {
    const map = mapHostSource()
    expect(map).toContain("map.on('style.load'")
    expect(map).toContain("if (!instance.getSource('osm-pois'))")
    expect(map).toContain("if (!instance.getSource('osm-polygons'))")
    expect(map).toContain("if (!instance.getLayer('osm-poi-circle'))")
    expect(map).toContain("if (!instance.getLayer('osm-polygons-fill'))")
  })

  it('restores the saved map view without resizing for each viewport read', () => {
    const map = mapHostSource()
    expect(map).toContain('center: mapStore.center')
    expect(map).toContain('zoom: mapStore.zoom')
    expect(map).toContain('bearing: mapStore.bearing')
    expect(map).not.toContain('instance.resize()')
  })

  it('creates layers once and updates long-lived GeoJSON sources with setData', () => {
    const map = mapHostSource()
    expect(map).toContain("instance.addSource('osm-pois'")
    expect(map).toContain("instance.addSource('osm-polygons'")
    expect(map).toContain('?.setData(points)')
    expect(map).toContain('?.setData(polygons)')
  })

  it('uses feature state only in paint expressions, never in layer filters', () => {
    const map = mapHostSource()
    const filterLines = map.split('\n').filter(line => line.includes('filter:'))
    expect(filterLines).not.toEqual(expect.arrayContaining([expect.stringContaining("['feature-state'")]))
    expect(map).toContain("'circle-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0]")
    expect(map).toContain("instance.addSource('selected-polygon-source'")
  })

  it('defensively removes peninsula features before rendering and from pickable layers', () => {
    const map = mapHostSource()
    expect(map).toContain('!shouldExcludeOsmFeature(feature)')
    expect(map).toContain("['!=', ['get', 'natural'], 'peninsula']")
    expect(map.indexOf('const safeFeatures')).toBeLessThan(map.indexOf('?.setData(points)'))
  })

  it('clusters points and zooms into a tapped cluster', () => {
    const map = mapHostSource()
    expect(map).toContain('clusterMaxZoom: 14')
    expect(map).toContain("id: 'osm-clusters'")
    expect(map).toContain('getClusterExpansionZoom')
  })

  it('uses central POI-first picking for points, clusters and polygons', () => {
    const map = mapHostSource()
    const picking = appFile('utils/mapFeaturePicking.ts')
    expect(map).toContain('pickMapEntityAtPoint(instance, event.point, tolerance)')
    expect(picking.indexOf("kind: 'point-poi'")).toBeLessThan(picking.indexOf("kind: 'cluster'"))
    expect(picking).toContain('INTERACTIVE_POLYGON_LAYERS')
    expect(picking).toContain("kind: 'interactive-polygon'")
    expect(picking).toContain('.sort((left, right) => right.priority - left.priority)')
    expect(map).toContain('mapSelection.selectOsm(feature)')
    expect(map).toContain("picked.kind === 'interactive-polygon'")
  })

  it('loads normalized details only after feature selection', () => {
    const store = appFile('stores/osmViewport.ts')
    const preview = appFile('components/osm/OsmFeatureSidebar.vue')
    expect(store).toContain('async loadDetail(feature: OsmViewportFeature)')
    expect(store).toContain('`/osm/features/${feature.properties.osm_type}/${feature.properties.osm_id}`')
    expect(preview).toContain('detailLoading')
    expect(preview).toContain('Auf OpenStreetMap ansehen')
  })

  it('offers OSM controls in the shared filter sheet', () => {
    const sidebar = appFile('components/layout/LeftSidebar.vue')
    const filter = appFile('components/filters/OsmFeatureFilter.vue')
    expect(sidebar).toContain('<OsmFeatureFilter')
    expect(filter).toContain('Orte und Einrichtungen anzeigen')
    expect(filter).toContain('Flächenobjekte anzeigen')
    expect(filter).toContain('Gebäude ab Zoom 17')
    expect(filter).toContain('osm.toggleCategory')
  })

  it('uses the central accessible switch for every binary GIS layer control', () => {
    const sidebar = appFile('components/layout/LeftSidebar.vue')
    const osmFilter = appFile('components/filters/OsmFeatureFilter.vue')
    const compactLayers = appFile('components/map/MapLayerControl.vue')
    const toggle = appFile('components/filters/GisFilterToggleRow.vue')
    const analysisLayers = moduleFile('components/AnalysisAreasLayerControls.vue')

    expect(sidebar).not.toContain('type="checkbox"')
    expect(sidebar.match(/<GisFilterToggleRow/g)).toHaveLength(1)
    expect(sidebar).toContain('v-model="mapStore.polygonsVisible"')
    expect(sidebar).toContain('slot="map.layers"')
    expect(analysisLayers).toContain('v-model="areas.visibility[item.type]"')
    expect(analysisLayers).toContain(':active-color="item.activeColor"')
    expect(sidebar).not.toContain(':color="item.color"')
    expect(sidebar).not.toContain('square-indicator')
    expect(analysisLayers).toContain('class="grid gap-1" aria-label="Administrative Gebietsgrenzen"')
    expect(sidebar).not.toContain('rounded-xl border border-slate-200 p-2" aria-label="Administrative Gebietsgrenzen"')
    expect(osmFilter.match(/<GisFilterToggleRow/g)).toHaveLength(3)
    expect(osmFilter.match(/type="checkbox"/g)).toHaveLength(1)
    expect(osmFilter).toContain(':disabled="!osmEnabled"')
    expect(compactLayers).not.toContain('type="checkbox"')
    expect(toggle).toContain('role="switch"')
    expect(toggle).toContain(':aria-checked="modelValue"')
    expect(toggle).toContain('min-h-[44px]')
  })

  it('shows viewport counts, truncation and local OSM data date', () => {
    const summary = appFile('components/analysis/ViewportOsmSummary.vue')
    expect(summary).toContain('Lokale, deduplizierte Daten im Kartenausschnitt')
    expect(summary).toContain('meta.summary')
    expect(summary).toContain('meta.canonical_summary')
    expect(summary).toContain('meta.truncated')
    expect(summary).toContain('meta.osm_data_updated_at')
  })
})
