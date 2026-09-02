import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { developerDocumentationPages, findDeveloperDocumentationPage } from '../app/config/developerDocumentation'
import { projectConfig } from '../app/config/project'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('developer documentation', () => {
  it('defines unique and complete technical pages', () => {
    const slugs = developerDocumentationPages.map(page => page.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    expect(developerDocumentationPages.every(page => page.title.trim() && page.description.trim())).toBe(true)
    expect(findDeveloperDocumentationPage('osm')?.title).toContain('OpenStreetMap')
    expect(findDeveloperDocumentationPage('assistant')).toBeUndefined()
    expect(findDeveloperDocumentationPage('deployment')?.title).toContain('Deployment')
  })

  it('uses the dedicated developer origin as canonical target', () => {
    expect(projectConfig.documentation.developerUrl).toBe('https://developer.stadtplaner.oklabflensburg.de')
    const seo = appFile('composables/useDeveloperDocumentationSeo.ts')
    expect(seo).toContain('projectConfig.documentation.developerUrl')
    expect(seo).toContain("robots: 'index,follow'")
  })

  it('keeps local developer routes and maps the production subdomain', () => {
    const middleware = appFile('middleware/developer-docs.global.ts')
    expect(middleware).toContain("const developerPrefix = '/dokumentation/entwickler'")
    expect(middleware).toContain("host === 'stadtplaner.oklabflensburg.de'")
    expect(middleware).toContain('redirectCode: 301')
    expect(appFile('pages/dokumentation/entwickler/index.vue')).toContain('<DeveloperDocsLayout')
    expect(appFile('pages/dokumentation/entwickler/[slug].vue')).toContain('findDeveloperDocumentationPage')
  })

  it('links deep technical references to the repository instead of duplicating them', () => {
    const links = developerDocumentationPages
      .flatMap(page => page.sections)
      .flatMap(section => section.blocks)
      .filter(block => block.type === 'links')
      .flatMap(block => block.type === 'links' ? block.items : [])
      .map(item => item.to)

    expect(links).toContain(`${projectConfig.github.url}/blob/main/docs/osm-data.md`)
    expect(links).toContain(`${projectConfig.github.url}/blob/main/docs/ci.md`)
    expect(links).toContain(`${projectConfig.github.url}/blob/main/docs/deployment.md`)
  })
})
