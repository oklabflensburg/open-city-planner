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

  it('keeps authenticated notification UI lazy', () => {
    const header = source('app/components/layout/AppHeader.vue')
    expect(header).toContain('<LazyNotificationBell')
  })

  it('loads MapLibre from map components rather than the app entry', () => {
    for (const componentSource of [
      source('app/composables/useMapCanvasHost.ts'),
      source('app/components/polygon/PolygonDetailMap.vue'),
      source('app/components/polygon/PolygonCreateMap.vue')
    ]) {
      expect(componentSource).toContain("import('maplibre-gl')")
      expect(componentSource).toContain("import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')")
      expect(componentSource).toContain('maplibregl.setWorkerUrl(worker.default)')
    }
  })
})
