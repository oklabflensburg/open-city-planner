import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const repositoryFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../../${path}`, import.meta.url)),
  'utf8'
)

describe('Analysis Areas final cutover workflow', () => {
  const workflow = repositoryFile('.github/workflows/module-contract.yml')
  const consumerProbe = repositoryFile('scripts/check_analysis_areas_port_consumer.py')

  it('installs the immutable release through Registry and the production installer', () => {
    expect(workflow).toContain('OCP_ANALYSIS_AREAS_VERSION: "1.5.2"')
    expect(workflow).toContain(
      'OCP_ANALYSIS_AREAS_SHA256: 835a2745da15cdc17587324e451ea1b922ae0628738603c7a061d62407d08d58'
    )
    expect(workflow).toContain('OCP_MODULE_REGISTRY_URL: https://packages.stadtplaner.oklabflensburg.de')
    expect(workflow).toContain('install-registry analysis-areas')
    expect(workflow).toContain('--expected-sha256 "${OCP_ANALYSIS_AREAS_SHA256}"')
    expect(workflow).toContain('"status":"already-installed"')
  })

  it('does not rebuild, inject or directly install Analysis Areas', () => {
    expect(workflow).not.toContain('repository: oklabflensburg/ocp-module-analysis-areas')
    expect(workflow).not.toContain('.external-analysis-areas')
    expect(workflow).not.toContain('bundle build')
    expect(workflow).not.toContain('PYTHONPATH')
    expect(workflow).not.toContain('pip install ocp-module-analysis-areas')
    expect(consumerProbe).not.toContain('sys.path')
  })

  it('covers disabled, enable, browser, disable and re-enable states', () => {
    const orderedMarkers = [
      'assert_analysis_areas_cutover.py disabled',
      'app.cli.modules enable analysis-areas',
      'playwright.cutover.config.ts',
      'app.cli.modules disable analysis-areas',
      'assert_analysis_areas_cutover.py disabled-after-migration',
      'Re-enable without reinstall or data import'
    ]
    let previous = -1
    for (const marker of orderedMarkers) {
      const position = workflow.indexOf(marker, previous + 1)
      expect(position).toBeGreaterThan(previous)
      previous = position
    }
  })
})
