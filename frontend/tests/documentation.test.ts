import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { documentationPages, documentationPaths } from '../app/config/documentation'
import {
  documentationPath,
  findDocumentationPage,
  getDocumentationGroups,
  getDocumentationNeighbors,
  searchDocumentation
} from '../app/utils/documentation'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('integrated documentation', () => {
  it('defines all requested public routes from one typed source', () => {
    expect(documentationPaths).toEqual([
      '/dokumentation',
      '/dokumentation/erste-schritte',
      '/dokumentation/karte',
      '/dokumentation/filter',
      '/dokumentation/openstreetmap',
      '/dokumentation/flaechen',
      '/dokumentation/flaechen-bearbeiten',
      '/dokumentation/fast-facts',
      '/dokumentation/benutzerkonto',
      '/dokumentation/oauth',
      '/dokumentation/rollen',
      '/dokumentation/verwaltung',
      '/dokumentation/administration',
      '/dokumentation/faq'
    ])
    expect(findDocumentationPage('karte')?.title).toBe('Karte bedienen')
  })

  it('groups navigation and resolves active page paths', () => {
    expect(getDocumentationGroups().map(group => group.label)).toEqual([
      'Einstieg', 'Karte und Daten', 'Flächen', 'Auswertung', 'Konto und Zugriff', 'Verwaltung', 'Hilfe'
    ])
    const page = findDocumentationPage('rollen')!
    expect(documentationPath(page)).toBe('/dokumentation/rollen')
    const sidebar = appFile('components/docs/DocsSidebar.vue')
    expect(sidebar).toContain(':aria-current="item.slug === activeSlug ? \'page\' : undefined"')
  })

  it('supports full-text search and an explicit empty state', () => {
    expect(searchDocumentation('autosave').some(result => result.page.slug === 'flaechen-bearbeiten')).toBe(true)
    expect(searchDocumentation('lokale datenbank').some(result => result.page.slug === 'openstreetmap')).toBe(true)
    expect(searchDocumentation('unauffindbarerbegriff')).toEqual([])
    expect(appFile('components/docs/DocsSearch.vue')).toContain('Keine passenden Dokumentationsseiten gefunden.')
  })

  it('offers keyboard search and responsive disclosure controls', () => {
    const search = appFile('components/docs/DocsSearch.vue')
    const layout = appFile('components/docs/DocsLayout.vue')
    expect(search).toContain("event.key.toLowerCase() === 'k'")
    expect(layout).toContain('aria-controls="docs-mobile-navigation"')
    expect(layout).toContain('aria-controls="docs-mobile-toc"')
    expect(layout).toContain(':aria-expanded="mobileNavigationOpen"')
  })

  it('renders stable section anchors and the table of contents from the same sections', () => {
    const ids = documentationPages.flatMap(page => page.sections.map(section => `${page.slug}:${section.id}`))
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.every(value => /^[a-z0-9-]*:[a-z0-9-]+$/.test(value))).toBe(true)
    expect(appFile('components/docs/DocsTableOfContents.vue')).toContain(':href="`#${section.id}`"')
    expect(appFile('components/docs/DocsContent.vue')).toContain(':id="section.id"')
  })

  it('provides breadcrumbs and previous/next navigation', () => {
    const first = documentationPages[0]!
    const middle = findDocumentationPage('fast-facts')!
    const last = documentationPages.at(-1)!
    expect(getDocumentationNeighbors(first).previous).toBeUndefined()
    expect(getDocumentationNeighbors(middle).previous).toBeDefined()
    expect(getDocumentationNeighbors(middle).next).toBeDefined()
    expect(getDocumentationNeighbors(last).next).toBeUndefined()
    const layout = appFile('components/docs/DocsLayout.vue')
    expect(appFile('components/layout/PageBreadcrumbs.vue')).toContain('aria-label="Breadcrumb"')
    expect(layout).toContain('<PageHeader')
    expect(layout).toContain('{ label: props.page.group }')
    expect(layout).toContain('aria-label="Weitere Dokumentationsseiten"')
  })

  it('marks protected content with reusable role badges', () => {
    expect(findDocumentationPage('verwaltung')?.audience).toBe('verwaltung')
    expect(findDocumentationPage('benutzerkonto')?.audience).toBe('login')
    expect(findDocumentationPage('administration')?.audience).toBe('superuser')
    const badge = appFile('components/docs/DocsRoleBadge.vue')
    expect(badge).toContain("verwaltung: 'Nur VERWALTUNG'")
    expect(badge).toContain("login: 'Anmeldung erforderlich'")
    expect(badge).toContain("superuser: 'Nur SUPERUSER'")
    expect(appFile('components/docs/DocsCallout.vue')).toContain('important: ShieldAlert')
  })

  it('keeps documentation pages map-free, indexable and linked globally', () => {
    expect(appFile('components/docs/DocsLayout.vue')).not.toContain('MapLibre')
    expect(appFile('composables/useDocumentationSeo.ts')).toContain("robots: 'index,follow'")
    expect(appFile('composables/useSiteNavigation.ts')).toContain("{ label: 'Dokumentation', to: '/dokumentation' }")
    expect(appFile('components/layout/AppHeader.vue')).toContain('route.path.startsWith(`${path}/`)')
  })

  it('supports optional real screenshots without requiring placeholder images', () => {
    const types = appFile('types/documentation.ts')
    const content = appFile('components/docs/DocsContent.vue')
    expect(types).toContain("type: 'image'")
    expect(content).toContain(':alt="block.alt"')
    expect(documentationPages.flatMap(page => page.sections).flatMap(section => section.blocks).some(block => block.type === 'image')).toBe(false)
  })
})
