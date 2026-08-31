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
  it('builds the reference composition before the disabled host', () => {
    const exampleBuild = workflow.indexOf('- name: Build Nuxt application with example module')
    const disabledBuild = workflow.indexOf('- name: Build Nuxt application without optional modules')

    expect(exampleBuild).toBeGreaterThanOrEqual(0)
    expect(exampleBuild).toBeLessThan(disabledBuild)
  })

  it('uses explicit module environments for every build state', () => {
    expect(step('Build Nuxt application with example module')).toContain('OCP_FRONTEND_MODULES: example-module')
    expect(step('Build Nuxt application without optional modules')).toContain("OCP_FRONTEND_MODULES: ''")
    expect(workflow).not.toContain('analysis-areas')
  })
})
