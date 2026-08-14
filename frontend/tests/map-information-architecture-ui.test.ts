import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('map information architecture', () => {
  it('keeps legend and OSM details out of the map overlay', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).not.toContain('<MapLegend')
    expect(map).not.toContain('<OsmFeatureSidebar')
    expect(map).not.toContain('<OsmFeaturePreview')
    expect(map).not.toContain('new Popup')
  })

  it('renders controls, layers and the dynamic legend in the left sidebar', () => {
    const sidebar = appFile('components/layout/LeftSidebar.vue')
    const legend = appFile('components/map/MapLegend.vue')
    expect(sidebar.indexOf('<AreaFilter')).toBeLessThan(sidebar.indexOf('Kartendarstellung'))
    expect(sidebar.indexOf('Kartendarstellung')).toBeLessThan(sidebar.indexOf('>Layer<'))
    expect(sidebar.indexOf('>Layer<')).toBeLessThan(sidebar.indexOf('<MapLegend'))
    expect(sidebar).toContain(':theme="mapStore.thematicStyle"')
    expect(legend).not.toMatch(/\b(?:absolute|fixed|overflow-y-auto)\b/)
    expect(legend).toContain('whitespace-normal')
  })

  it('prioritizes OSM and polygon selections before analytics in the right sidebar', () => {
    const sidebar = appFile('components/layout/RightSidebar.vue')
    expect(sidebar.indexOf('<OsmFeatureSidebar')).toBeLessThan(sidebar.indexOf('<PolygonStatistics'))
    expect(sidebar.indexOf('<PolygonStatistics')).toBeLessThan(sidebar.indexOf('<FastFacts'))
  })

  it('derives one exclusive polygon, OSM or null selection from existing stores', () => {
    const selection = appFile('composables/useMapSelection.ts')
    expect(selection).toContain("{ type: 'polygon'")
    expect(selection).toContain("{ type: 'osm'")
    expect(selection).toContain('| null')
    expect(selection.indexOf('osmStore.clearSelection()')).toBeLessThan(selection.indexOf('polygonStore.selectPolygon(id)'))
    expect(selection.indexOf('polygonStore.clearSelection()')).toBeLessThan(selection.indexOf('osmStore.select(feature)'))
  })

  it('selects OSM features, clears both selections on empty map clicks and opens the mobile selection sheet', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('mapSelection.selectOsm(feature)')
    expect(map).toContain('mapSelection.clearSelection()')
    expect(map).toContain("mapStore.openMobilePanel('analytics')")
    expect(map).toContain('mapSelection.selectPolygon(id)')
  })

  it('puts the legend in the mobile filter sheet and OSM details in the selection sheet', () => {
    const shell = appFile('components/layout/AppShell.vue')
    const left = appFile('components/layout/LeftSidebar.vue')
    const right = appFile('components/layout/RightSidebar.vue')
    expect(shell).toContain("mapStore.activeMobilePanel === 'filter'")
    expect(shell).toContain("mapStore.activeMobilePanel === 'analytics'")
    expect(shell).toContain('<LeftSidebar')
    expect(shell).toContain('<RightSidebar')
    expect(left).toContain('<MapLegend')
    expect(right).toContain('<OsmFeatureSidebar')
  })
})
