import { describe, expect, it } from 'vitest'
import {
  filterOKLabProjects,
  okLabProjectCategories,
  okLabProjects
} from '~/config/okLabProjects'

describe('OK Lab project gallery', () => {
  it('contains all 18 current projects with unique slugs and valid required links', () => {
    expect(okLabProjects).toHaveLength(18)
    expect(new Set(okLabProjects.map(project => project.slug)).size).toBe(18)

    for (const project of okLabProjects) {
      expect(new URL(project.codeForGermanyUrl).protocol).toBe('https:')
      expect(new URL(project.githubUrl).hostname).toBe('github.com')
      expect(project.thumbnail).toMatch(/^\/open-data\/projects\/.+\.webp$/)
      if (project.websiteUrl) expect(new URL(project.websiteUrl).protocol).toBe('https:')
      if (project.dataSourceUrl) expect(new URL(project.dataSourceUrl).protocol).toBe('https:')
    }
  })

  it('keeps the official category set and project status values', () => {
    expect(okLabProjectCategories).toEqual([
      'Freizeit', 'Gesellschaft', 'Kultur', 'Mobilität', 'Naturschutz',
      'Politik', 'Technologie', 'Umwelt', 'Verwaltung', 'Wohnen'
    ])
    expect(okLabProjects.some(project => project.status === 'completed')).toBe(true)
    expect(okLabProjects.some(project => project.status === 'in-progress')).toBe(true)
    expect(okLabProjects.some(project => project.status === 'contributors-wanted')).toBe(true)
  })

  it('filters case-insensitively across title, description and category', () => {
    expect(filterOKLabProjects(okLabProjects, 'BAUM', '')).toHaveLength(1)
    expect(filterOKLabProjects(okLabProjects, '', 'Mobilität').map(project => project.slug)).toEqual([
      'nahverkehr-flensburg', 'unfallkarte-flensburg'
    ])
    expect(filterOKLabProjects(okLabProjects, 'karte', 'Kultur').map(project => project.slug)).toEqual([
      'kulturnacht-karte', 'denkmalkarte-schleswig-holstein'
    ])
    expect(filterOKLabProjects(okLabProjects, 'existiert nicht', '')).toEqual([])
  })

  it('renders optional links, a real-image path and the neutral fallback conditionally', () => {
    const card = readFileSync(fileURLToPath(new URL('../app/components/open-data/OpenDataProjectCard.vue', import.meta.url)), 'utf8')
    expect(card).toContain('v-if="project.websiteUrl"')
    expect(card).toContain('v-if="project.githubUrl"')
    expect(card).toContain('v-if="project.dataSourceUrl"')
    expect(card).toContain('v-if="project.thumbnail"')
    expect(card).toContain('v-else')
    expect(card).not.toContain('line-clamp')
  })

  it('renders the local projects during SSR and exposes collection SEO', () => {
    const page = readFileSync(fileURLToPath(new URL('../app/pages/open-data.vue', import.meta.url)), 'utf8')
    expect(page).toContain('v-for="project in filteredProjects"')
    expect(page).not.toContain('onMounted')
    expect(page).toContain("'@type': 'CollectionPage'")
    expect(page).toContain("'@type': 'ItemList'")
    expect(page).toContain("path: '/open-data'")
  })
})
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
