import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function mapHostSource() {
  return [
    'app/components/map/MapCanvas.vue',
    'app/composables/useMapCanvasHost.ts',
    'app/map-runtime/MapLifecycle.ts',
    'app/map-runtime/LayerRegistry.ts'
  ].map(path => resolve(process.cwd(), path))
    .filter(existsSync)
    .map(path => readFileSync(path, 'utf8'))
    .join('\n')
}

describe('MapCanvas legacy behavior characterization', () => {
  const source = mapHostSource()

  it('keeps MapLibre client-only initialization and lifecycle recovery', () => {
    expect(source).toContain("import('maplibre-gl')")
    expect(source).toContain("map.on('load'")
    expect(source).toContain("map.on('style.load'")
    expect(source).toContain("instance.on('moveend'")
    expect(source).toContain('runtime.destroy()')
  })

  it('restores current sources, layers and deterministic overlay ordering', () => {
    for (const sourceId of ['osm-pois', 'osm-polygons', 'overview-polygons', 'selected-polygon-source']) {
      expect(source).toContain(`addSource('${sourceId}'`)
    }
    for (const layerId of ['osm-poi-circle', 'osm-polygons-fill', 'overview-polygons-fill', 'selected-polygon-outline']) {
      expect(source).toContain(`id: '${layerId}'`)
    }
    expect(source).toContain('ensureStadtplanerLayerOrder(instance)')
  })

  it('retains picking, highlighting, feature details and mobile selection UI', () => {
    expect(source).toContain('pickMapEntityAtPoint(instance')
    expect(source).toContain('updatePolygonHover')
    expect(source).toContain('mapSelection.selectOsm')
    expect(source).toContain('mapSelection.selectPolygon')
    expect(source).toContain("window.matchMedia('(max-width: 1279px)')")
    expect(source).toContain("mapStore.openGisPanel('selection')")
  })

  it('keeps module-owned layers out of the generic MapCanvas host', () => {
    const canvas = readFileSync(resolve(process.cwd(), 'app/components/map/MapCanvas.vue'), 'utf8')
    expect(canvas).not.toContain('analysis-areas')
  })

  it('retains viewport debounce, stale-result guard and resize handling', () => {
    expect(source).toContain('clearTimeout(osmViewportTimer)')
    expect(source).toContain('osmStore.covers(viewport, zoom)')
    expect(source).toContain('map.value === instance')
    expect(source).toContain('this.#resizeObserver.observe(container)')
    expect(source).toContain("map.value.once('idle'")
  })

  it('keeps Terra Draw client-only in the existing polygon editor maps', () => {
    const createMap = readFileSync(resolve(process.cwd(), 'app/components/polygon/PolygonCreateMap.vue'), 'utf8')
    const detailMap = readFileSync(resolve(process.cwd(), 'app/components/polygon/PolygonDetailMap.vue'), 'utf8')
    expect(createMap).toContain("import('terra-draw')")
    expect(createMap).toContain("terra.setMode('polygon')")
    expect(detailMap).toContain('new terraDraw.TerraDrawSelectMode')
    expect(detailMap).toContain("terra.on('change'")
  })
})
