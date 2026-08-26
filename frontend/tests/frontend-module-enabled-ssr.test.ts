import { fileURLToPath } from 'node:url'
import { fetch, setup } from '@nuxt/test-utils/e2e'
import { afterAll, describe, expect, it } from 'vitest'

process.env.OCP_FRONTEND_MODULES = 'example-module'

await setup({
  rootDir: fileURLToPath(new URL('..', import.meta.url)),
  browser: false,
  port: 3013,
  setupTimeout: 180_000,
  env: { NUXT_PUBLIC_SITE_URL: 'https://stadtplaner.example' }
})

afterAll(() => {
  delete process.env.OCP_FRONTEND_MODULES
})

describe('enabled frontend module SSR', () => {
  it('renders module navigation and the component slot in the host SSR shell', async () => {
    const response = await fetch('/')
    expect(response.status).toBe(200)
    const html = await response.text()
    expect(html).toContain('aria-label="Hauptnavigation"')
    expect(html).toContain('href="/module-example"')
    expect(html).toContain('Beispielmodul')
    expect(html).toContain('data-ui-slot="header.actions"')
    expect(html).toContain('data-ui-contribution="example-module.header-action"')
    expect(html).toContain('aria-label="Frontend-Modulbeispiel öffnen"')
  })

  it('renders the discovered layer page with shared host primitives, active navigation and SEO', async () => {
    const response = await fetch('/module-example')
    expect(response.status).toBe(200)
    const html = await response.text()
    expect(html).toContain('Frontend-Modulbeispiel')
    expect(html).toContain('Gemeinsame Host-Primitives')
    expect(html).toContain('Der gemeinsame Pinia-Store wurde 0 Mal aktualisiert.')
    expect(html).toContain('data-example-module-card')
    expect(html).toMatch(/(?:href="\/module-example"[^>]*aria-current="page"|aria-current="page"[^>]*href="\/module-example")/)
    expect(html).toContain('<title>Frontend-Modulbeispiel – OK Lab Flensburg</title>')
    expect(html).toContain('content="noindex,nofollow"')
  })
})
