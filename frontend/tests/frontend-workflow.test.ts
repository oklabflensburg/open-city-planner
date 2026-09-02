import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const workflow = readFileSync(
  fileURLToPath(new URL('../../.github/workflows/frontend.yml', import.meta.url)),
  'utf8'
)

const step = (name: string) => {
  const start = workflow.indexOf(`- name: ${name}`)
  expect(start).toBeGreaterThanOrEqual(0)
  const next = workflow.indexOf('\n      - name:', start + 1)
  return workflow.slice(start, next === -1 ? undefined : next)
}

describe('Frontend production workflow', () => {
  it('audits the domain-free production build after the example module build', () => {
    const preflight = workflow.indexOf('- name: Validate production module configuration')
    const exampleBuild = workflow.indexOf('- name: Build Nuxt application with example module')
    const productionBuild = workflow.indexOf('- name: Build production Nuxt application without domain modules')
    const audit = workflow.indexOf('- name: Audit production SSR metadata')

    expect(preflight).toBeLessThan(exampleBuild)
    expect(exampleBuild).toBeLessThan(productionBuild)
    expect(productionBuild).toBeLessThan(audit)
    expect(workflow.slice(productionBuild, audit).match(/run: pnpm build/g)).toHaveLength(1)
  })

  it('uses explicit module environments for every build state', () => {
    for (const name of [
      'Validate production module configuration',
      'Build production Nuxt application without domain modules',
      'Audit production SSR metadata'
    ]) {
      expect(step(name)).toContain("OCP_FRONTEND_MODULES: ''")
      expect(step(name)).not.toContain('OCP_BACKEND_MODULES:')
    }

    expect(step('Resolve backend module inventory')).toContain('scripts/backend-module-inventory --format env')
    expect(step('Resolve backend module inventory')).toContain("ENABLED_MODULES: ''")
    expect(step('Build Nuxt application with example module')).toContain('OCP_FRONTEND_MODULES: example-module')
    expect(workflow).not.toContain('analysis-areas@1.0.0')
  })
})
