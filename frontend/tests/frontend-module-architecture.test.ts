import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { activeFrontendViolations, scanFrontendArchitecture, scanModuleImportBoundaries } from '../module-host/import-boundaries'

const repositoryRoot = resolve(import.meta.dirname, '../..')

describe('frontend module architecture gate', () => {
  it('keeps production host and modules independent', () => {
    expect(activeFrontendViolations({ repositoryRoot })).toEqual([])
  }, 15_000)

  it('detects a foreign re-export with a stable rule ID', () => {
    const fixtureRoot = resolve(import.meta.dirname, 'fixtures/module-contracts/broken-import')
    expect(scanFrontendArchitecture({ repositoryRoot: fixtureRoot, frontendRoot: fixtureRoot }))
      .toContainEqual(expect.objectContaining({
        rule: 'ARCH-FE-MODULE-001',
        source: 'frontend-modules/alpha/layer/app/pages/alpha.vue',
        target: '../../../../beta/layer/internal/secret'
      }))
  })

  it('returns non-zero for the committed broken import fixture', () => {
    const fixtureRoot = resolve(import.meta.dirname, 'fixtures/module-contracts/broken-import')
    const result = spawnSync(
      process.execPath,
      [resolve(import.meta.dirname, '../module-host/check-architecture.ts')],
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          OCP_ARCHITECTURE_ROOT: fixtureRoot,
          OCP_ARCHITECTURE_FRONTEND_ROOT: fixtureRoot
        }
      }
    )

    expect(result.status).toBe(1)
    expect(result.stderr).toContain('ARCH-FE-MODULE-001')
    expect(result.stderr).toContain('alpha/layer/app/pages/alpha.vue')
  })

  it('checks extracted installable packages and every static import form', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-installed-frontend-'))
    const layer = resolve(root, 'analysis-areas/layer/app')
    mkdirSync(layer, { recursive: true })
    writeFileSync(resolve(layer, 'private.ts'), [
      `import '~/stores/map'`,
      `export { value } from '@/utils/private'`,
      `const lazy = () => import('~/app/private')`,
      `const legacy = require('../../../outside')`
    ].join('\n'))

    expect(scanModuleImportBoundaries(resolve(root, 'analysis-areas'), layer).map(item => item.target))
      .toEqual(['~/stores/map', '@/utils/private', '~/app/private', '../../../outside'])
  })

  it('rejects unbound private host auto-import calls in TypeScript and Vue scripts', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-private-auto-imports-'))
    const layer = resolve(root, 'analysis-areas/layer/app')
    mkdirSync(layer, { recursive: true })
    writeFileSync(resolve(layer, 'private.ts'), [
      'const map = useMapStore()',
      'const auth = useAuthStore()',
      'const filters = useFilterStore()'
    ].join('\n'))
    writeFileSync(resolve(layer, 'private.js'), 'const api = useApi()\n')
    writeFileSync(resolve(layer, 'private.vue'), [
      '<script setup lang="ts">',
      'const selection = useMapSelection()',
      '</script>',
      '<template><span /></template>'
    ].join('\n'))

    const violations = scanModuleImportBoundaries(resolve(root, 'analysis-areas'), layer)
    expect(violations.map(item => [item.target, item.reason])).toEqual([
      ['useApi', 'private-host-auto-import'],
      ['useMapStore', 'private-host-auto-import'],
      ['useAuthStore', 'private-host-auto-import'],
      ['useFilterStore', 'private-host-auto-import'],
      ['useMapSelection', 'private-host-auto-import']
    ])
  })

  it('allows public Nuxt auto-imports and locally shadowed host-like names', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-public-auto-imports-'))
    const layer = resolve(root, 'analysis-areas/layer/app')
    mkdirSync(layer, { recursive: true })
    writeFileSync(resolve(layer, 'public.ts'), [
      "const route = useRoute()",
      "const state = useState('x')",
      'function useMapStore() { return {} }',
      'const localMap = useMapStore()'
    ].join('\n'))
    writeFileSync(resolve(layer, 'imported.ts'), [
      "import { useAuthStore } from './local-auth'",
      'useAuthStore()',
      'function invoke(useFilterStore: () => unknown) { return useFilterStore() }'
    ].join('\n'))
    writeFileSync(resolve(layer, 'sdk-imported.ts'), [
      "import { mapCursorValue } from '#frontend-module-sdk'",
      'mapCursorValue()'
    ].join('\n'))
    writeFileSync(resolve(layer, 'public.vue'), [
      '<script>const useMapSelection = () => ({})</script>',
      '<script setup lang="ts">function invoke(useApi: () => unknown) { return useApi() }</script>',
      '<template><span /></template>'
    ].join('\n'))

    expect(scanModuleImportBoundaries(resolve(root, 'analysis-areas'), layer)).toEqual([])
  })

  it('derives arbitrary private composables, utilities and stores from the selected host root', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-auto-import-root-'))
    const frontendRoot = resolve(root, 'frontend')
    const moduleRoot = resolve(frontendRoot, 'frontend-modules/demo')
    const layer = resolve(moduleRoot, 'layer/app')
    mkdirSync(resolve(frontendRoot, 'app/composables'), { recursive: true })
    mkdirSync(resolve(frontendRoot, 'app/utils'), { recursive: true })
    mkdirSync(resolve(frontendRoot, 'app/stores'), { recursive: true })
    mkdirSync(layer, { recursive: true })
    writeFileSync(resolve(frontendRoot, 'app/composables/polygon.ts'), 'export function usePolygonApi() { return {} }\nexport const useGisInvalidation = () => undefined\n')
    writeFileSync(resolve(frontendRoot, 'app/utils/private.ts'), 'export function privateHelper() {}\n')
    writeFileSync(resolve(frontendRoot, 'app/stores/auth.ts'), 'export const useAuthStore = () => ({})\n')
    writeFileSync(resolve(layer, 'consumer.ts'), 'usePolygonApi()\nuseGisInvalidation()\nprivateHelper()\nuseAuthStore()\n')

    expect(scanModuleImportBoundaries(moduleRoot, layer, { frontendRoot }).map(item => item.target))
      .toEqual(['usePolygonApi', 'useGisInvalidation', 'privateHelper', 'useAuthStore'])
  })

  it('rejects a real host utility when it is called as an unbound auto-import', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-real-host-utility-'))
    const moduleRoot = resolve(root, 'analysis-areas')
    const layer = resolve(moduleRoot, 'layer/app')
    mkdirSync(layer, { recursive: true })
    writeFileSync(resolve(layer, 'consumer.ts'), 'mapCursorValue()\n')

    expect(scanModuleImportBoundaries(moduleRoot, layer)).toEqual([
      expect.objectContaining({ target: 'mapCursorValue', reason: 'private-host-auto-import' })
    ])
  })

  it('allows module-owned auto-imports from composables, utilities and stores', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-module-auto-imports-'))
    const frontendRoot = resolve(root, 'frontend')
    const moduleRoot = resolve(frontendRoot, 'frontend-modules/demo')
    const layer = resolve(moduleRoot, 'layer/app')
    mkdirSync(resolve(layer, 'composables'), { recursive: true })
    mkdirSync(resolve(layer, 'utils'), { recursive: true })
    mkdirSync(resolve(layer, 'stores'), { recursive: true })
    writeFileSync(resolve(layer, 'composables/local.ts'), 'export function useLocalApi() { return {} }\n')
    writeFileSync(resolve(layer, 'utils/local.ts'), 'export function moduleHelper() {}\n')
    writeFileSync(resolve(layer, 'stores/local.ts'), 'export const useLocalStore = () => ({})\n')
    writeFileSync(resolve(layer, 'consumer.ts'), 'useLocalApi()\nmoduleHelper()\nuseLocalStore()\n')

    expect(scanModuleImportBoundaries(moduleRoot, layer, { frontendRoot })).toEqual([])
  })

  it('rejects host and module auto-import name collisions at their declaration', () => {
    const root = mkdtempSync(resolve(tmpdir(), 'ocp-module-auto-import-collision-'))
    const frontendRoot = resolve(root, 'frontend')
    const moduleRoot = resolve(frontendRoot, 'frontend-modules/demo')
    const hostUtils = resolve(frontendRoot, 'app/utils')
    const moduleUtils = resolve(moduleRoot, 'layer/app/utils')
    mkdirSync(hostUtils, { recursive: true })
    mkdirSync(moduleUtils, { recursive: true })
    writeFileSync(resolve(hostUtils, 'shared.ts'), 'export function sharedHelper() {}\n')
    writeFileSync(resolve(moduleUtils, 'shared.ts'), 'export function sharedHelper() {}\n')

    expect(scanModuleImportBoundaries(moduleRoot, moduleRoot, { frontendRoot })).toEqual([
      expect.objectContaining({ target: 'sharedHelper', reason: 'private-host-auto-import' })
    ])
  })

  it('keeps host auto-import indexes isolated between frontend roots', () => {
    const createFixture = (name: string, exportedName: string) => {
      const frontendRoot = resolve(mkdtempSync(resolve(tmpdir(), `ocp-${name}-`)), 'frontend')
      const moduleRoot = resolve(frontendRoot, 'frontend-modules/demo')
      const layer = resolve(moduleRoot, 'layer/app')
      mkdirSync(resolve(frontendRoot, 'app/composables'), { recursive: true })
      mkdirSync(layer, { recursive: true })
      writeFileSync(resolve(frontendRoot, 'app/composables/private.ts'), `export const ${exportedName} = () => ({})\n`)
      writeFileSync(resolve(layer, 'consumer.ts'), 'useFirstRoot()\nuseSecondRoot()\n')
      return { frontendRoot, moduleRoot, layer }
    }
    const first = createFixture('first-root', 'useFirstRoot')
    const second = createFixture('second-root', 'useSecondRoot')

    expect(scanModuleImportBoundaries(first.moduleRoot, first.layer, { frontendRoot: first.frontendRoot }).map(item => item.target)).toEqual(['useFirstRoot'])
    expect(scanModuleImportBoundaries(second.moduleRoot, second.layer, { frontendRoot: second.frontendRoot }).map(item => item.target)).toEqual(['useSecondRoot'])
  })
})
