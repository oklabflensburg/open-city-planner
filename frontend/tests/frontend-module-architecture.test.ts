import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { activeFrontendViolations, scanFrontendArchitecture } from '../module-host/import-boundaries'

const repositoryRoot = resolve(import.meta.dirname, '../..')

describe('frontend module architecture gate', () => {
  it('keeps production host and modules independent', () => {
    expect(activeFrontendViolations({ repositoryRoot })).toEqual([])
  })

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
})
import { spawnSync } from 'node:child_process'
