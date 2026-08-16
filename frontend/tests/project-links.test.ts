import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { documentationPages } from '~/config/documentation'
import { projectConfig } from '~/config/project'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('official project links', () => {
  it('defines valid repository, issues and contribution URLs centrally', () => {
    expect(projectConfig.github.repository).toBe('oklabflensburg/open-city-planner')
    expect(projectConfig.github.url).toBe('https://github.com/oklabflensburg/open-city-planner')
    expect(new URL(projectConfig.github.issuesUrl).pathname).toBe('/oklabflensburg/open-city-planner/issues')
    expect(new URL(projectConfig.github.contributingUrl).pathname).toBe('/oklabflensburg/open-city-planner/blob/main/CONTRIBUTING.md')
  })

  it('uses one accessible external-link component with safe browser attributes', () => {
    const component = appFile('components/project/GitHubLink.vue')
    expect(component).toContain("from '~/config/project'")
    expect(component).toContain('target="_blank"')
    expect(component).toContain('rel="noopener noreferrer"')
    expect(component).toContain('öffnet in einem neuen Tab')
    expect(component).toContain('<Github')
    expect(component).toContain('<ExternalLink')
  })

  it('places the repository link in the footer and contextual public pages', () => {
    expect(appFile('components/layout/AppFooter.vue')).toContain('<GitHubLink variant="footer"')

    const about = appFile('pages/ueber-das-projekt.vue')
    expect(about).toContain('<ContentSection title="Open Source"')
    expect(about).toContain('<GitHubLink variant="button"')
    expect(about).toContain('destination="contributing"')
    expect(about).toContain('destination="issues"')

    const openData = appFile('pages/open-data.vue')
    expect(openData).toContain('Stadtplaner ist Open Source')
    expect(openData).toContain('<GitHubLink variant="button"')
  })

  it('links the repository from the documentation landing page and API page', () => {
    const overview = documentationPage('')
    const api = documentationPage('api')

    expect(overview.sections.some(section => section.id === 'quellcode-und-entwicklung')).toBe(true)
    expect(api.sections.some(section => section.id === 'quellcode')).toBe(true)

    for (const page of [overview, api]) {
      const links = page.sections.flatMap(section => section.blocks.flatMap(block => block.type === 'links' ? block.items : []))
      expect(links.some(link => link.to === projectConfig.github.url)).toBe(true)
    }

    const content = appFile('components/docs/DocsContent.vue')
    expect(content).toContain(":target=\"isExternalLink(item.to) ? '_blank' : undefined\"")
    expect(content).toContain(":rel=\"isExternalLink(item.to) ? 'noopener noreferrer' : undefined\"")
  })
})

function documentationPage(slug: string) {
  // Kept below the tests so the assertions above remain focused on the feature.
  return documentationPages.find(page => page.slug === slug)!
}
