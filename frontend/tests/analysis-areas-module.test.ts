import { fileURLToPath } from 'node:url'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { resolveFrontendModules } from '../module-host/discovery'
import { createMapExtensionDefinitionRegistry } from '../module-host/map-definition-registry'
import { createFrontendContributionRegistry } from '../module-host/ui-registry'

const options = {
  modulesDirectory: fileURLToPath(new URL('../frontend-modules', import.meta.url)),
  appPagesDirectory: fileURLToPath(new URL('../app/pages', import.meta.url)),
  backendModules: 'analysis-areas'
}

describe('Analysis Areas frontend module', () => {
  it('removes routes, navigation and map contributions when disabled', () => {
    const modules = resolveFrontendModules({ ...options, enabledModules: '' })
    expect(modules).toEqual([])
    expect(createFrontendContributionRegistry(modules, []).all()).toEqual([])
    expect(createMapExtensionDefinitionRegistry(modules).snapshot()).toEqual({
      sources: [],
      layers: []
    })
  })

  it('owns the production routes and primary navigation when enabled', () => {
    const modules = resolveFrontendModules({ ...options, enabledModules: 'analysis-areas' })
    expect(modules[0]?.publicContributions.routes.map(route => route.path)).toEqual([
      '/gebiete',
      '/gebiete/:slug'
    ])
    expect(createFrontendContributionRegistry(modules, []).all()).toContainEqual(
      expect.objectContaining({
        id: 'analysis-areas.primary-navigation',
        to: '/gebiete'
      })
    )
  })

  it('contributes the area source, boundary layers and interaction control', () => {
    const modules = resolveFrontendModules({ ...options, enabledModules: 'analysis-areas' })
    const map = createMapExtensionDefinitionRegistry(modules).snapshot()
    expect(map.sources.map(source => source.id)).toEqual(['analysis-areas.data'])
    expect(map.layers.map(layer => layer.id)).toContain('analysis-areas.quarter-fill')
    expect(modules[0]?.publicContributions.ui).toContainEqual(expect.objectContaining({
      id: 'analysis-areas.map-runtime',
      slot: 'map.controls'
    }))
    const layerConfig = readFileSync(fileURLToPath(new URL(
      '../frontend-modules/analysis-areas/layer/nuxt.config.ts',
      import.meta.url
    )), 'utf8')
    expect(layerConfig).toContain('global: true')
  })
})
