import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import {
  FrontendModuleError,
  discoverFrontendModules,
  resolveFrontendModules
} from '../module-host/discovery'
import { FRONTEND_MODULE_SDK_VERSION } from '../module-host/contract'

const temporaryDirectories: string[] = []

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) rmSync(directory, { recursive: true, force: true })
})

function fixture() {
  const root = mkdtempSync(resolve(tmpdir(), 'ocp-frontend-modules-'))
  temporaryDirectories.push(root)
  const modulesDirectory = resolve(root, 'modules')
  const appPagesDirectory = resolve(root, 'app/pages')
  mkdirSync(modulesDirectory, { recursive: true })
  mkdirSync(appPagesDirectory, { recursive: true })
  return { root, modulesDirectory, appPagesDirectory }
}

function addModule(
  modulesDirectory: string,
  directoryName: string,
  definition: Record<string, unknown> = {}
) {
  const id = String(definition.id ?? directoryName)
  const moduleRoot = resolve(modulesDirectory, directoryName)
  const contributions = definition.publicContributions as { routes?: Array<{ path: string, source: string }> } | undefined
  const routeSource = contributions?.routes?.[0]?.source ?? `layer/app/pages/${id}.vue`
  mkdirSync(resolve(moduleRoot, routeSource, '..'), { recursive: true })
  writeFileSync(resolve(moduleRoot, routeSource), '<template><p>fixture</p></template>')
  writeFileSync(resolve(moduleRoot, 'module.json'), JSON.stringify({
    schemaVersion: 1,
    id,
    version: '1.0.0',
    compatibility: { host: '>=1.0.0 <2.0.0', sdk: '>=1.0.0 <2.0.0' },
    layer: 'layer',
    requires: { modules: {} },
    publicContributions: { routes: [{ path: `/${id}`, source: routeSource }] },
    ...definition
  }))
}

describe('frontend build-time module host', () => {
  it('discovers enabled modules, ignores disabled modules and orders deterministically', () => {
    const paths = fixture()
    addModule(paths.modulesDirectory, 'zeta')
    addModule(paths.modulesDirectory, 'alpha')

    expect(discoverFrontendModules(paths.modulesDirectory).map(module => module.id)).toEqual(['alpha', 'zeta'])
    expect(resolveFrontendModules({ ...paths, enabledModules: 'zeta,alpha' }).map(module => module.id)).toEqual(['alpha', 'zeta'])
    expect(resolveFrontendModules({ ...paths, enabledModules: '' })).toEqual([])
  })

  it('fails for missing enabled modules', () => {
    const paths = fixture()
    expect(() => resolveFrontendModules({ ...paths, enabledModules: 'missing' }))
      .toThrowError(/Enabled frontend module "missing" was not found/)
  })

  it('reports duplicate IDs with both manifest sources', () => {
    const paths = fixture()
    addModule(paths.modulesDirectory, 'first', { id: 'duplicate' })
    addModule(paths.modulesDirectory, 'second', { id: 'duplicate' })
    expect(() => discoverFrontendModules(paths.modulesDirectory)).toThrowError(
      new RegExp(`Duplicate frontend module ID "duplicate".*first/module.json.*second/module.json`)
    )
  })

  it('accepts compatible SDK versions and rejects incompatible versions', () => {
    const paths = fixture()
    addModule(paths.modulesDirectory, 'compatible')
    expect(FRONTEND_MODULE_SDK_VERSION).toBe('1.2.0')
    expect(resolveFrontendModules({ ...paths, enabledModules: 'compatible' })).toHaveLength(1)

    addModule(paths.modulesDirectory, 'future', {
      compatibility: { host: '>=1.0.0 <2.0.0', sdk: '>=2.0.0 <3.0.0' }
    })
    expect(() => resolveFrontendModules({ ...paths, enabledModules: 'future' }))
      .toThrowError(/requires frontend module SDK >=2.0.0 <3.0.0, but found 1.2.0/)
  })

  it('requires one shared module ID and validates an explicit backend inventory', () => {
    const mismatched = fixture()
    addModule(mismatched.modulesDirectory, 'statistics', { backendModuleId: 'polygons' })
    expect(() => discoverFrontendModules(mismatched.modulesDirectory))
      .toThrowError(/full-stack modules must share one stable module ID/)

    const paths = fixture()
    addModule(paths.modulesDirectory, 'statistics', {
      backendModuleId: 'statistics',
      compatibility: { host: '>=1.0.0 <2.0.0', sdk: '>=1.0.0 <2.0.0', backend: '>=2.0.0 <3.0.0' }
    })
    expect(() => resolveFrontendModules({ ...paths, enabledModules: 'statistics', backendModules: '' }))
      .toThrowError(/requires enabled backend module "statistics"/)
    expect(() => resolveFrontendModules({ ...paths, enabledModules: 'statistics', backendModules: 'statistics@1.0.0' }))
      .toThrowError(/requires backend module >=2.0.0 <3.0.0, but found 1.0.0/)
    expect(resolveFrontendModules({ ...paths, enabledModules: 'statistics', backendModules: 'statistics@2.1.0' }))
      .toHaveLength(1)
  })

  it('places required modules first and rejects missing dependencies', () => {
    const paths = fixture()
    addModule(paths.modulesDirectory, 'base')
    addModule(paths.modulesDirectory, 'consumer', { requires: { modules: { base: '>=1.0.0 <2.0.0' } } })
    expect(resolveFrontendModules({ ...paths, enabledModules: 'consumer,base' }).map(module => module.id))
      .toEqual(['base', 'consumer'])
    expect(() => resolveFrontendModules({ ...paths, enabledModules: 'consumer' }))
      .toThrowError(/requires enabled module "base"/)
  })

  it('rejects route collisions between modules and host pages', () => {
    const moduleCollision = fixture()
    addModule(moduleCollision.modulesDirectory, 'first', {
      publicContributions: { routes: [{ path: '/shared', source: 'layer/app/pages/shared.vue' }] }
    })
    addModule(moduleCollision.modulesDirectory, 'second', {
      publicContributions: { routes: [{ path: '/shared', source: 'layer/app/pages/shared.vue' }] }
    })
    expect(() => resolveFrontendModules({ ...moduleCollision, enabledModules: 'first,second' }))
      .toThrowError(/Route collision for "\/shared".*first.*second/)

    const hostCollision = fixture()
    writeFileSync(resolve(hostCollision.appPagesDirectory, 'reserved.vue'), '<template />')
    addModule(hostCollision.modulesDirectory, 'reserved')
    expect(() => resolveFrontendModules({ ...hostCollision, enabledModules: 'reserved' }))
      .toThrowError(/Route collision for "\/reserved".*host pages.*reserved/)
  })

  it('rejects local sources that escape the module directory', () => {
    const paths = fixture()
    addModule(paths.modulesDirectory, 'unsafe', { layer: '../outside' })
    expect(() => discoverFrontendModules(paths.modulesDirectory)).toThrowError(FrontendModuleError)
    expect(() => discoverFrontendModules(paths.modulesDirectory)).toThrowError(/must remain inside/)
  })

  it('rejects undeclared pages and host-owned layer contributions', () => {
    const undeclared = fixture()
    addModule(undeclared.modulesDirectory, 'example')
    writeFileSync(resolve(undeclared.modulesDirectory, 'example/layer/app/pages/hidden.vue'), '<template />')
    expect(() => discoverFrontendModules(undeclared.modulesDirectory)).toThrowError(/contains undeclared page/)

    const plugin = fixture()
    addModule(plugin.modulesDirectory, 'example')
    mkdirSync(resolve(plugin.modulesDirectory, 'example/layer/app/plugins'), { recursive: true })
    expect(() => discoverFrontendModules(plugin.modulesDirectory)).toThrowError(/may not provide host-owned layer path "app\/plugins"/)
  })

  it('rejects foreign module imports, arbitrary HTML payloads and foreign component sources', () => {
    const foreignImport = fixture()
    addModule(foreignImport.modulesDirectory, 'alpha')
    writeFileSync(
      resolve(foreignImport.modulesDirectory, 'alpha/layer/app/pages/alpha.vue'),
      `<script setup>import value from '../../../../beta/internal'</script><template>{{ value }}</template>`
    )
    expect(() => discoverFrontendModules(foreignImport.modulesDirectory))
      .toThrowError(/imports outside its own module/)

    const arbitraryHtml = fixture()
    addModule(arbitraryHtml.modulesDirectory, 'alpha', {
      publicContributions: {
        routes: [{ path: '/alpha', source: 'layer/app/pages/alpha.vue' }],
        ui: [{ id: 'alpha.unsafe', slot: 'header.actions', html: '<script>alert(1)</script>' }]
      }
    })
    expect(() => discoverFrontendModules(arbitraryHtml.modulesDirectory))
      .toThrowError(/Frontend module definition .* is invalid/)

    const foreignComponent = fixture()
    addModule(foreignComponent.modulesDirectory, 'alpha', {
      publicContributions: {
        routes: [{ path: '/alpha', source: 'layer/app/pages/alpha.vue' }],
        ui: [{
          id: 'alpha.widget',
          slot: 'dashboard.widgets',
          component: 'ForeignWidget',
          source: '../beta/layer/app/components/ForeignWidget.vue'
        }]
      }
    })
    expect(() => discoverFrontendModules(foreignComponent.modulesDirectory))
      .toThrowError(/must remain inside/)
  })

  it('keeps Nuxt generic and forbids runtime microfrontend loading', () => {
    const nuxtConfig = readFileSync(resolve(import.meta.dirname, '../nuxt.config.ts'), 'utf8')
    const discovery = readFileSync(resolve(import.meta.dirname, '../module-host/discovery.ts'), 'utf8')
    expect(nuxtConfig).toContain('resolveFrontendModules')
    expect(nuxtConfig).toContain('extends: frontendModules.length')
    expect(nuxtConfig).toContain('frontendModules.map(module => module.layerPath)')
    expect(nuxtConfig).not.toContain('example-module')
    expect(`${nuxtConfig}\n${discovery}`).not.toMatch(/(?:https?:\/\/.*\.m?js|module federation|createElement\(['"]script|\beval\(|new Function\()/i)
  })
})
