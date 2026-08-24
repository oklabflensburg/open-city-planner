import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = resolve(import.meta.dirname, '..')
const source = (path: string) => readFileSync(resolve(root, path), 'utf8')

describe('frontend bundle boundaries', () => {
  it('prefetches global routes on intent instead of visibility', () => {
    const config = source('nuxt.config.ts')
    expect(config).toContain('prefetchOn: { visibility: false, interaction: true }')
    expect(config).not.toContain('chunkSizeWarningLimit')
    expect(config).not.toContain('manualChunks')
  })

  it('mounts GIS URL history with the map application instead of globally', () => {
    expect(existsSync(resolve(root, 'app/plugins/gis-filters.client.ts'))).toBe(false)
    expect(source('app/components/layout/AppShell.vue')).toContain('useGisFilterHistory()')
  })

  it('keeps authenticated notification UI and charts lazy', () => {
    const header = source('app/components/layout/AppHeader.vue')
    const sidebar = source('app/components/layout/RightSidebar.vue')
    expect(header).toContain('<LazyNotificationBell')
    expect(sidebar).toContain('<LazyIndustryChart')
    expect(sidebar).toContain("() => import('~/components/analysis/DistributionCharts.vue')")
  })

  it('loads MapLibre from map components rather than the app entry', () => {
    for (const component of [
      'app/components/map/MapCanvas.vue',
      'app/components/polygon/PolygonDetailMap.vue',
      'app/components/analysis/AnalysisAreaDetailMap.vue',
      'app/components/polygon/PolygonCreateMap.vue'
    ]) {
      const componentSource = source(component)
      expect(componentSource).toContain("import('maplibre-gl')")
      expect(componentSource).toContain("import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')")
      expect(componentSource).toContain('maplibregl.setWorkerUrl(worker.default)')
    }
  })
})
