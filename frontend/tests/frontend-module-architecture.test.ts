import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs'
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

    expect(scanModuleImportBoundaries(resolve(root, 'analysis-areas'), layer)).toEqual([])
  })
})
import { spawnSync } from 'node:child_process'
