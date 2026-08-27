import { createServer } from 'node:http'
import { fileURLToPath } from 'node:url'
import { fetch, setup } from '@nuxt/test-utils/e2e'
import { afterAll, describe, expect, it } from 'vitest'

const api = createServer((request, response) => {
  response.setHeader('content-type', 'application/json')
  if (request.url === '/api/v1/modules/reference/items') {
    response.end(JSON.stringify([{
      id: 'marker-1',
      title: 'SSR-Referenzmarker',
      description: 'Antwort der lokalen Test-API',
      longitude: 9.43,
      latitude: 54.79
    }]))
    return
  }
  response.statusCode = 404
  response.end('{}')
})

await new Promise<void>(resolve => api.listen(0, '127.0.0.1', resolve))
const address = api.address()
if (!address || typeof address === 'string') throw new Error('Reference API test server failed.')
const apiBaseUrl = `http://127.0.0.1:${address.port}/api/v1`

process.env.OCP_FRONTEND_MODULES = 'analysis-areas,example-module,reference'
process.env.OCP_BACKEND_MODULES = 'analysis-areas@1.0.0,reference@1.0.0'
process.env.NUXT_API_INTERNAL_BASE_URL = apiBaseUrl
process.env.NUXT_PUBLIC_API_BASE_URL = apiBaseUrl

await setup({
  rootDir: fileURLToPath(new URL('..', import.meta.url)),
  browser: false,
  port: 3013,
  setupTimeout: 180_000,
  env: { NUXT_PUBLIC_SITE_URL: 'https://stadtplaner.example' }
})

afterAll(async () => {
  delete process.env.OCP_FRONTEND_MODULES
  delete process.env.OCP_BACKEND_MODULES
  delete process.env.NUXT_API_INTERNAL_BASE_URL
  delete process.env.NUXT_PUBLIC_API_BASE_URL
  api.closeAllConnections()
  await new Promise<void>((resolve, reject) => {
    api.close(error => error ? reject(error) : resolve())
  })
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

  it('renders the reference module API page and map slot through the host', async () => {
    const page = await fetch('/referenzmodul')
    expect(page.status).toBe(200)
    const pageHtml = await page.text()
    expect(pageHtml).toContain('SSR-Referenzmarker')
    expect(pageHtml).toContain('href="/referenzmodul"')
    expect(pageHtml).toContain('<title>Referenzmodul – OK Lab Flensburg</title>')

    const map = await fetch('/karte')
    expect(map.status).toBe(200)
    const mapHtml = await map.text()
    expect(mapHtml).toContain('data-ui-contribution="reference.map-feature-info"')
    expect(mapHtml).toContain('Informationen zu Referenzmarkern')
  })
})
