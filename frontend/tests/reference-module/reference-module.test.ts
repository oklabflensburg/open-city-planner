import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { resolveFrontendModules } from '../../module-host/discovery'
import { createMapExtensionDefinitionRegistry } from '../../module-host/map-definition-registry'
import { createFrontendContributionRegistry } from '../../module-host/ui-registry'
import {
  createReferenceFeatureInfoProvider,
  referenceSelectionFrom
} from '../../frontend-modules/reference/layer/app/composables/useReferenceFeatureInfo'
import { referenceApiUrl } from '../../frontend-modules/reference/layer/app/composables/referenceApi'
import { isUiContributionVisible } from '../../module-host/public'

const options = {
  modulesDirectory: fileURLToPath(new URL('../../frontend-modules', import.meta.url)),
  appPagesDirectory: fileURLToPath(new URL('../../app/pages', import.meta.url)),
  backendModules: 'reference@1.0.0'
}

describe('reference frontend module contract fixture', () => {
  it('is absent when disabled and resolves as a compatible full-stack module when enabled', () => {
    expect(resolveFrontendModules({ ...options, enabledModules: '' })).toEqual([])
    const modules = resolveFrontendModules({ ...options, enabledModules: 'reference' })
    expect(modules.map(module => module.id)).toEqual(['reference'])
    expect(modules[0]?.layerPath).toBe(
      fileURLToPath(new URL('../../frontend-modules/reference/layer', import.meta.url))
    )
  })

  it('contributes its route, navigation, slot, API-backed source and layer', () => {
    const modules = resolveFrontendModules({ ...options, enabledModules: 'reference' })
    const ui = createFrontendContributionRegistry(modules, ['/']).all()
    const map = createMapExtensionDefinitionRegistry(modules).snapshot()

    expect(modules[0]?.publicContributions.routes).toContainEqual(expect.objectContaining({
      path: '/referenzmodul'
    }))
    expect(ui.map(contribution => contribution.id)).toEqual([
      'reference.map-feature-info',
      'reference.primary-navigation',
      'reference.admin-navigation'
    ])
    expect(map.sources).toContainEqual(expect.objectContaining({
      id: 'reference.items',
      source: expect.objectContaining({
        data: expect.objectContaining({ type: 'FeatureCollection', features: [] })
      })
    }))
    expect(map.layers).toContainEqual(expect.objectContaining({
      id: 'reference.items',
      sourceId: 'reference.items'
    }))
  })

  it('uses the configured API origin and keeps management navigation permission-aware', () => {
    expect(referenceApiUrl('https://api.example/api/v1/', '.geojson'))
      .toBe('https://api.example/api/v1/modules/reference/items.geojson')
    const modules = resolveFrontendModules({ ...options, enabledModules: 'reference' })
    const contribution = createFrontendContributionRegistry(modules, ['/']).all()
      .find(item => item.id === 'reference.admin-navigation')
    expect(contribution).toBeDefined()
    if (!contribution) return
    const visibility = {
      authenticated: true,
      featureEnabled: () => true,
      moduleEnabled: () => true
    }
    expect(isUiContributionVisible(contribution, { ...visibility, can: () => false })).toBe(false)
    expect(isUiContributionVisible(contribution, { ...visibility, can: permission => permission === 'reference.items-write' })).toBe(true)
  })

  it('selects its rendered feature and resolves title and description', async () => {
    const selection = referenceSelectionFrom({
      type: 'click',
      features: [{
        id: 'marker-1',
        properties: { title: 'Hafen', description: 'Beispielmarker' },
        geometry: { type: 'Point', coordinates: [9.43, 54.79] }
      }]
    })
    expect(selection).toEqual(expect.objectContaining({
      moduleId: 'reference',
      layerId: 'reference.items',
      featureId: 'marker-1'
    }))
    expect(selection).not.toBeNull()
    if (!selection) return
    const provider = createReferenceFeatureInfoProvider()
    expect(provider.canHandle(selection)).toBe(true)
    expect(await provider.resolveFeatureInfo(selection, {} as never)).toEqual({
      title: 'Hafen',
      description: 'Beispielmarker'
    })
  })
})
