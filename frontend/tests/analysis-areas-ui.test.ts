import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appFile = (path: string) => readFileSync(resolve(process.cwd(), 'app', path), 'utf8')

describe('hierarchical analysis areas', () => {
  it('contributes three zoom-dependent administrative layers with module-owned click priority', () => {
    const manifest = JSON.parse(readFileSync(
      resolve(process.cwd(), 'frontend-modules/analysis-areas/module.json'),
      'utf8'
    ))
    const runtime = readFileSync(
      resolve(process.cwd(), 'frontend-modules/analysis-areas/layer/app/components/AnalysisAreasMapRuntime.vue'),
      'utf8'
    )
    const picking = appFile('utils/mapFeaturePicking.ts')
    const layers = manifest.publicContributions.map.layers
    expect(layers.find((layer: { id: string }) => layer.id === 'analysis-areas.municipality-fill').layer.minzoom).toBe(7)
    expect(layers.find((layer: { id: string }) => layer.id === 'analysis-areas.district-fill').layer.minzoom).toBe(9.5)
    expect(layers.find((layer: { id: string }) => layer.id === 'analysis-areas.quarter-fill').layer.minzoom).toBe(11.5)
    expect(runtime).toContain("id: 'analysis-areas.select'")
    expect(runtime).toContain('priority: 20')
    expect(runtime.indexOf("'analysis-areas.quarter-fill'")).toBeLessThan(runtime.indexOf("'analysis-areas.district-fill'"))
    expect(runtime.indexOf("'analysis-areas.district-fill'")).toBeLessThan(runtime.indexOf("'analysis-areas.municipality-fill'"))
    expect(picking).not.toContain("featureType: 'QUARTER'")
    expect(picking).toContain("featureType: 'STADTPLANNER'")
    expect(picking).toContain("featureType: 'OSM_POLYGON'")
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
    expect(shell).toContain("mapStore.openGisPanel('analytics')")
  })
})
