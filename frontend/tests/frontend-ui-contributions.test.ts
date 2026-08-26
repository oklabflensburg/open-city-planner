import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { FrontendModuleUiContribution, UiVisibilityContext } from '../module-host/ui-contract'
import {
  DuplicateUiContributionError,
  FrontendContributionError,
  FrontendContributionRegistry,
  isUiContributionVisible
} from '../module-host/ui-registry'
import { composeNavigation } from '../app/composables/useSiteNavigation'
import { hasPermissionSnapshot } from '../app/utils/permissions'

const publicContext: UiVisibilityContext = {
  authenticated: false,
  can: () => false,
  featureEnabled: () => false,
  moduleEnabled: moduleId => moduleId === 'alpha'
}

function navigation(
  id: string,
  slot: 'navigation.primary' | 'navigation.user' | 'navigation.admin' = 'navigation.primary',
  priority?: number
): FrontendModuleUiContribution {
  return { id, slot, label: id, to: '/known', priority }
}

describe('frontend UI contribution registry', () => {
  it('binds ownership and registers multiple contributions', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    const registrar = registry.registrar('alpha', 0)
    registrar.register(navigation('alpha.primary'))
    registrar.register({
      id: 'alpha.header-action',
      slot: 'header.actions',
      component: 'AlphaAction',
      source: 'layer/app/components/AlphaAction.vue',
      accessibleLabel: 'Alpha öffnen'
    })
    expect(registry.seal().all()).toHaveLength(2)
    expect(registry.all().every(item => item.moduleId === 'alpha')).toBe(true)
  })

  it('sorts by ascending priority, module order and stable ID', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    registry.registrar('beta', 1).register(navigation('beta.late-id', 'navigation.primary', 100))
    registry.registrar('alpha', 0).register(navigation('alpha.second', 'navigation.primary', 100))
    registry.registrar('alpha', 0).register(navigation('alpha.first', 'navigation.primary', 100))
    registry.registrar('beta', 1).register(navigation('beta.early-priority', 'navigation.primary', 10))
    expect(registry.seal().all().map(item => item.id)).toEqual([
      'beta.early-priority',
      'alpha.first',
      'alpha.second',
      'beta.late-id'
    ])
  })

  it('rejects duplicate IDs with both owners and slots', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    registry.registrar('alpha', 0).register(navigation('alpha.shared'))
    expect(() => registry.registrar('beta', 1).register({
      ...navigation('alpha.shared', 'navigation.user')
    })).toThrowError(DuplicateUiContributionError)
    expect(() => registry.registrar('beta', 1).register({
      ...navigation('alpha.shared', 'navigation.user')
    })).toThrowError(/alpha\.shared.*navigation\.primary.*alpha.*navigation\.user.*beta/)
  })

  it('rejects unknown slots, forged ownership and broken static routes', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    const registrar = registry.registrar('alpha', 0)
    expect(() => registrar.register({ ...navigation('alpha.unknown'), slot: 'unknown.slot' } as never))
      .toThrowError(/Unknown UI slot/)
    expect(() => registrar.register(navigation('beta.forged')))
      .toThrowError(/stable owner prefix "alpha\."/)
    expect(() => registrar.register({ ...navigation('alpha.broken'), to: '/missing' }))
      .toThrowError(/unknown static route/)
  })

  it('requires accessible labels for module map controls', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    const registrar = registry.registrar('alpha', 0)
    expect(() => registrar.register({
      id: 'alpha.map-control',
      slot: 'map.controls',
      component: 'AlphaMapControl',
      source: 'layer/app/components/AlphaMapControl.vue',
      accessibleLabel: ''
    })).toThrow(/requires an accessible label/)
    registrar.register({
      id: 'alpha.accessible-map-control',
      slot: 'map.controls',
      component: 'AlphaMapControl',
      source: 'layer/app/components/AlphaMapControl.vue',
      accessibleLabel: 'Kartenwerkzeug öffnen'
    })
    expect(registry.seal().forSlot('map.controls')).toHaveLength(1)
  })

  it('is read-only after sealing and cannot be read before sealing', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    const registrar = registry.registrar('alpha', 0)
    expect(() => registry.all()).toThrowError(/must be sealed/)
    registrar.register(navigation('alpha.primary'))
    registry.seal()
    expect(() => registrar.register(navigation('alpha.late'))).toThrowError(/after the registry was sealed/)
    expect(Object.isFrozen(registry.all())).toBe(true)
    expect(Object.isFrozen(registry.all()[0])).toBe(true)
  })

  it('supports public, auth, permission, feature and module-state visibility', () => {
    const contribution = (visibility?: FrontendModuleUiContribution['visibility']) => ({
      ...navigation('alpha.visibility'),
      moduleId: 'alpha',
      moduleOrder: 0,
      visibility
    })
    expect(isUiContributionVisible(contribution(), publicContext)).toBe(true)
    expect(isUiContributionVisible(contribution({ auth: 'authenticated' }), publicContext)).toBe(false)
    expect(isUiContributionVisible(contribution({ auth: 'anonymous' }), publicContext)).toBe(true)
    expect(isUiContributionVisible(contribution({ permission: 'alpha.read' }), publicContext)).toBe(false)
    expect(isUiContributionVisible(contribution({ feature: 'alpha.preview' }), publicContext)).toBe(false)
    expect(isUiContributionVisible(contribution({ module: 'alpha' }), publicContext)).toBe(true)
    expect(isUiContributionVisible(contribution({ module: 'beta' }), publicContext)).toBe(false)

    const authorized = {
      ...publicContext,
      authenticated: true,
      can: (permission: string) => permission === 'alpha.read',
      featureEnabled: (feature: string) => feature === 'alpha.preview'
    }
    expect(isUiContributionVisible(contribution({ auth: 'authenticated', permission: 'alpha.read', feature: 'alpha.preview' }), authorized)).toBe(true)
    expect(isUiContributionVisible(contribution({ auth: 'anonymous' }), authorized)).toBe(false)
  })

  it('uses only the backend permission snapshot and defaults to deny', () => {
    const user = {
      is_superuser: false,
      permissions: ['social.publish', 'example-module.admin']
    } as never
    expect(hasPermissionSnapshot(user, 'social.publish')).toBe(true)
    expect(hasPermissionSnapshot(user, 'unknown.permission')).toBe(false)
    expect(hasPermissionSnapshot({ is_superuser: true } as never, 'social.publish')).toBe(false)
    expect(hasPermissionSnapshot(null, 'social.publish')).toBe(false)
  })

  it('composes host and primary, user and admin module navigation deterministically', () => {
    const registry = new FrontendContributionRegistry(['/known'])
    const registrar = registry.registrar('alpha', 0)
    registrar.register(navigation('alpha.primary', 'navigation.primary', 150))
    registrar.register(navigation('alpha.user', 'navigation.user'))
    registrar.register(navigation('alpha.admin', 'navigation.admin'))
    registry.seal()

    const primary = composeNavigation([{ label: 'Host', to: '/known' }], registry.forSlot('navigation.primary') as never)
    expect(primary.map(item => item.id)).toEqual(['host.known', 'alpha.primary'])
    expect(registry.forSlot('navigation.user')).toHaveLength(1)
    expect(registry.forSlot('navigation.admin')).toHaveLength(1)
  })

  it('keeps the host generic and exposes no arbitrary HTML payload', () => {
    const hostSources = [
      '../nuxt.config.ts',
      '../app/composables/useSiteNavigation.ts',
      '../app/components/layout/AppHeader.vue',
      '../app/components/layout/MobileNavigation.vue',
      '../app/components/ui/UiContributionSlot.vue'
    ].map(path => readFileSync(resolve(import.meta.dirname, path), 'utf8')).join('\n')
    const contract = readFileSync(resolve(import.meta.dirname, '../module-host/ui-contract.ts'), 'utf8')
    expect(hostSources).not.toContain('example-module')
    expect(hostSources).not.toContain('ExampleModuleAction')
    expect(contract).not.toMatch(/\bhtml\??:/)
    expect(contract).not.toMatch(/remote|iframe|script/i)
  })
})
