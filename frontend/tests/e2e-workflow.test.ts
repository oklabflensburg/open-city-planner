import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const repositoryFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../../${path}`, import.meta.url)),
  'utf8'
)

describe('E2E workflow module configuration', () => {
  const workflow = repositoryFile('.github/workflows/e2e.yml')

  it('starts both webservers with the domain-free Host inventory', () => {
    expect(workflow).toMatch(/^  ENABLED_MODULES: ''$/m)
    expect(workflow).toMatch(/^  OCP_FRONTEND_MODULES: ''$/m)
    expect(workflow).toMatch(/^  CORS_ORIGINS: http:\/\/127\.0\.0\.1:3010$/m)
    expect(workflow).toContain('install-registry analysis-areas')
    expect(workflow).toContain('--version 1.0.0')
    expect(workflow).toContain('7006f31ea73f40e38f63d2065652c27ad5d3391ddcc8cfad2f149993efef3dcf')
    expect(workflow).toContain('scripts/backend-module-inventory --format env')

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
    expect(workflow).toContain('app.cli.module_migrations upgrade')
    expect(workflow).not.toContain('uv run alembic upgrade head')
  })

  it('keeps backend CI independent from the Settings default', () => {
    const backendWorkflow = repositoryFile('.github/workflows/backend.yml')
    expect(backendWorkflow).toMatch(/^  ENABLED_MODULES: ''$/m)
    expect(backendWorkflow).toContain('install-registry analysis-areas')
    expect(backendWorkflow).toContain('--version 1.0.0')
    expect(backendWorkflow).toContain('app.cli.module_migrations preflight')
    expect(backendWorkflow).toContain('app.cli.module_migrations upgrade')
    expect(backendWorkflow).not.toContain('uv run alembic upgrade head')
  })
})
