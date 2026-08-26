import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { resolveFrontendModules } from '../module-host/discovery'
import { MapExtensionDefinitionError, MapExtensionDefinitionRegistry, createMapExtensionDefinitionRegistry } from '../module-host/map-definition-registry'

describe('frontend module Map SDK', () => {
  it('binds ownership, seals definitions and sorts layers deterministically', () => {
    const registry = new MapExtensionDefinitionRegistry()
    const registrar = registry.registrar('alpha', 0)
    registrar.registerSource({ id: 'alpha.data', source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } })
    registrar.registerLayer({ id: 'alpha.labels', sourceId: 'alpha.data', group: 'labels', layer: { type: 'symbol' } })
    registrar.registerLayer({ id: 'alpha.fill', sourceId: 'alpha.data', group: 'analysis', layer: { type: 'fill' } })
    expect(registry.seal().snapshot().layers.map(layer => layer.id)).toEqual(['alpha.fill', 'alpha.labels'])
    expect(() => registrar.registerSource({ id: 'alpha.late', source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } }))
      .toThrow(/after the registry was sealed/)
  })

  it('fails fast for duplicate, forged and unknown source IDs', () => {
    const registry = new MapExtensionDefinitionRegistry()
    const alpha = registry.registrar('alpha', 0)
    alpha.registerSource({ id: 'alpha.data', source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } })
    expect(() => alpha.registerSource({ id: 'alpha.data', source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } }))
      .toThrow(MapExtensionDefinitionError)
    expect(() => alpha.registerSource({ id: 'beta.data', source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } }))
      .toThrow(/owner prefix "alpha\."/)
    expect(() => alpha.registerLayer({ id: 'alpha.layer', sourceId: 'alpha.unknown', group: 'overlay', layer: { type: 'circle' } }))
      .toThrow(/unknown source/)
  })

  it('loads the example extension only when its module is enabled', () => {
    const options = {
      modulesDirectory: resolve(import.meta.dirname, '../frontend-modules'),
      appPagesDirectory: resolve(import.meta.dirname, '../app/pages')
    }
    expect(createMapExtensionDefinitionRegistry(resolveFrontendModules({ ...options, enabledModules: '' })).snapshot().layers).toHaveLength(0)
    const enabled = createMapExtensionDefinitionRegistry(resolveFrontendModules({ ...options, enabledModules: 'example-module' })).snapshot()
    expect(enabled.sources.map(source => source.id)).toEqual(['example-module.landmark'])
    expect(enabled.layers.map(layer => layer.id)).toEqual(['example-module.landmark'])
  })

  it('keeps MapCanvas generic and exposes raw MapLibre only through the explicit escape hatch', () => {
    const mapCanvas = readFileSync(resolve(import.meta.dirname, '../app/components/map/MapCanvas.vue'), 'utf8')
    const contract = readFileSync(resolve(import.meta.dirname, '../module-host/map-contract.ts'), 'utf8')
    expect(mapCanvas).not.toContain('example-module')
    expect(contract).toContain('unsafeMapLibre()')
    expect(contract).not.toMatch(/readonly map:\s*MapLibreMap/)
  })
})
