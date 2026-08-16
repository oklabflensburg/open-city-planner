import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('hierarchical analysis areas', () => {
  it('renders three zoom-dependent administrative layers below city polygons and OSM click priority', () => {
    const map = appFile('components/map/MapCanvas.vue')
    const picking = appFile('utils/mapFeaturePicking.ts')
    expect(map).toContain("type: 'MUNICIPALITY', minzoom: 7")
    expect(map).toContain("type: 'DISTRICT', minzoom: 9.5")
    expect(map).toContain("type: 'QUARTER', minzoom: 11.5")
    expect(picking.indexOf('MAP_INTERACTIVE_LAYERS.osmPolygons')).toBeLessThan(picking.indexOf('MAP_INTERACTIVE_LAYERS.analysisAreas'))
    expect(picking.indexOf('MAP_INTERACTIVE_LAYERS.cityplannerPolygons')).toBeLessThan(picking.indexOf('MAP_INTERACTIVE_LAYERS.analysisAreas'))
  })

  it('uses one shared selection abstraction and responsive sidebars', () => {
    const selection = appFile('composables/useMapSelection.ts')
    const left = appFile('components/layout/LeftSidebar.vue')
    const right = appFile('components/layout/RightSidebar.vue')
    const content = appFile('components/map/MapSelectionContent.vue')
    const shell = appFile('components/layout/AppShell.vue')
    expect(selection).toContain("type: 'analysis-area'")
    expect(selection).toContain('selectAnalysisArea')
    expect(left).toContain('analysisAreasStore.visibility')
    expect(right).toContain('<MapSelectionContent />')
    expect(content).toContain('<AnalysisAreaCard')
    expect(shell).toContain("mapStore.openMobilePanel('analytics')")
  })
})
