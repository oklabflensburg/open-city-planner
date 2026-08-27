import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { resolveFrontendModules } from '../../module-host/discovery'
import { scanFrontendArchitecture } from '../../module-host/import-boundaries'

const repositoryRoot = resolve(import.meta.dirname, '../../..')
const temporaryDirectories: string[] = []

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true })
  }
})

function generateScaffold(moduleId = 'hello-world') {
  const root = mkdtempSync(resolve(tmpdir(), 'ocp-module-scaffold-'))
  temporaryDirectories.push(root)
  for (const directory of [
    'backend/app/modules',
    'backend/tests/modules',
    'frontend/frontend-modules',
    'frontend/tests',
    'frontend/app/pages'
  ]) {
    mkdirSync(resolve(root, directory), { recursive: true })
  }

  const result = spawnSync(
    'python3',
    [resolve(repositoryRoot, 'scripts/create-module'), moduleId, '--root', root],
    { encoding: 'utf8' }
  )
  expect(result.error).toBeUndefined()
  expect(result.status, result.stderr).toBe(0)

  return {
    root,
    frontendRoot: resolve(root, 'frontend'),
    modulesDirectory: resolve(root, 'frontend/frontend-modules'),
    appPagesDirectory: resolve(root, 'frontend/app/pages')
  }
}

describe('generated frontend module scaffold', () => {
  it('satisfies real discovery, manifest and contribution contracts', () => {
    const paths = generateScaffold()

    const modules = resolveFrontendModules({
      modulesDirectory: paths.modulesDirectory,
      appPagesDirectory: paths.appPagesDirectory,
      enabledModules: 'hello-world',
      backendModules: 'hello-world@1.0.0'
    })

    expect(modules).toHaveLength(1)
    expect(modules[0]).toMatchObject({
      id: 'hello-world',
      backendModuleId: 'hello-world',
      publicContributions: {
        routes: [{
          path: '/modules/hello-world',
          source: 'layer/app/pages/modules/hello-world.vue'
        }]
      }
    })
  })

  it('passes the real frontend architecture scanner', () => {
    const paths = generateScaffold()

    expect(scanFrontendArchitecture({
      repositoryRoot: paths.root,
      frontendRoot: paths.frontendRoot
    })).toEqual([])
  })
})
