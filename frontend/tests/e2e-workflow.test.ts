import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const repositoryFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../../${path}`, import.meta.url)),
  'utf8'
)

describe('E2E workflow module configuration', () => {
  const workflow = repositoryFile('.github/workflows/e2e.yml')

  it('starts both webservers with the production module inventory', () => {
    expect(workflow).toMatch(/^  ENABLED_MODULES: analysis-areas$/m)
    expect(workflow).toMatch(/^  OCP_FRONTEND_MODULES: analysis-areas$/m)
    expect(workflow).toMatch(/^  OCP_BACKEND_MODULES: analysis-areas@1\.0\.0$/m)

    const playwright = repositoryFile('frontend/playwright.config.ts')
    expect(playwright).toContain('-m uvicorn app.main:app')
    expect(playwright).toContain('pnpm dev --host 127.0.0.1 --port 3010')
  })

  it('validates both module runtimes before Playwright', () => {
    const frontendPreflight = workflow.indexOf('- name: Verify E2E frontend module configuration')
    const backendPreflight = workflow.indexOf('- name: Verify E2E backend module configuration')
    const playwright = workflow.indexOf('- name: Run Playwright')

    expect(frontendPreflight).toBeGreaterThanOrEqual(0)
    expect(backendPreflight).toBeGreaterThanOrEqual(0)
    expect(frontendPreflight).toBeLessThan(playwright)
    expect(backendPreflight).toBeLessThan(playwright)
    expect(workflow.slice(frontendPreflight, backendPreflight)).toContain('run: pnpm modules:check')
    expect(workflow.slice(backendPreflight, playwright)).toContain('app.cli.module_migrations preflight')
  })

  it('keeps backend CI independent from the Settings default', () => {
    expect(repositoryFile('.github/workflows/backend.yml')).toMatch(/^  ENABLED_MODULES: analysis-areas$/m)
  })
})
