import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('hierarchical analysis areas', () => {
  it('renders three zoom-dependent administrative layers below city polygons and OSM click priority', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain("type: 'MUNICIPALITY', minzoom: 7")
    expect(map).toContain("type: 'DISTRICT', minzoom: 9.5")
    expect(map).toContain("type: 'QUARTER', minzoom: 11.5")
    expect(map.indexOf("feature.layer.id === 'overview-polygons-fill'")).toBeLessThan(map.indexOf('mapSelection.selectAnalysisArea'))
    expect(map.indexOf('mapSelection.selectOsm(feature)')).toBeLessThan(map.indexOf('mapSelection.selectAnalysisArea'))
  })

  it('uses one shared selection abstraction and responsive sidebars', () => {
    const selection = appFile('composables/useMapSelection.ts')
    const left = appFile('components/layout/LeftSidebar.vue')
    const right = appFile('components/layout/RightSidebar.vue')
    const shell = appFile('components/layout/AppShell.vue')
    expect(selection).toContain("type: 'analysis-area'")
    expect(selection).toContain('selectAnalysisArea')
    expect(left).toContain('analysisAreasStore.visibility')
    expect(right).toContain('<AnalysisAreaCard />')
    expect(shell).toContain("mapStore.openMobilePanel('analytics')")
  })
})
