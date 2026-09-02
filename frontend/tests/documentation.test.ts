import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { documentationGroupOrder, documentationPages, documentationPaths } from '../app/config/documentation'
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
      '/dokumentation/benutzerkonto',
      '/dokumentation/benachrichtigungen',
      '/dokumentation/rollen',
      '/dokumentation/administration',
      '/dokumentation/api'
    ])
    expect(findDocumentationPage('karte')?.title).toBe('Karte bedienen')
  })

  it('groups navigation and resolves active page paths', () => {
    expect(getDocumentationGroups().map(group => group.label)).toEqual([
      'Einstieg', 'Karte und Daten', 'Konto und Bearbeitung', 'Hilfe', 'Quellcode und Entwicklung'
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

  it('findet zentrale Themen mit deutschen Suchbegriffen und Synonymen', () => {
    expect(searchDocumentation('Gebäude').some(result => result.page.slug === 'openstreetmap')).toBe(true)
    expect(searchDocumentation('Leerstand').some(result => result.page.slug === 'flaechen')).toBe(true)
    expect(searchDocumentation('lokale Datenbank').some(result => result.page.slug === 'openstreetmap')).toBe(true)
  })

  it('hält Slugs, Metadaten, Gruppen und interne Dokumentationslinks gültig', () => {
    const slugs = documentationPages.map(page => page.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    expect(documentationPages.every(page => page.title.trim() && page.description.trim())).toBe(true)
    expect(documentationPages.every(page => documentationGroupOrder.includes(page.group as typeof documentationGroupOrder[number]))).toBe(true)

    const documentationLinks = documentationPages
      .flatMap(page => page.sections)
      .flatMap(section => section.blocks)
      .filter(block => block.type === 'links')
      .flatMap(block => block.type === 'links' ? block.items : [])
      .map(item => item.to)
      .filter(to => to.startsWith('/dokumentation'))

    expect(documentationLinks.every((target) => {
      const [path, anchor] = target.split('#')
      if (!path || !documentationPaths.includes(path)) return false
      if (!anchor) return true
      const linkedPage = documentationPages.find(page => documentationPath(page) === path)
      return linkedPage?.sections.some(section => section.id === anchor) === true
    })).toBe(true)
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
    const middle = findDocumentationPage('flaechen')!
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
    expect(findDocumentationPage('rollen')?.audience).toBe('verwaltung')
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

  it('enthält keine gebrochenen relativen Markdown-Dateilinks', () => {
    const root = fileURLToPath(new URL('../../', import.meta.url))
    const docsDirectory = resolve(root, 'docs')
    const markdownFiles = [
      resolve(root, 'README.md'),
      resolve(root, 'CONTRIBUTING.md'),
      resolve(root, 'backend/README.md'),
      resolve(root, 'frontend/README.md'),
      ...readdirSync(docsDirectory, { recursive: true })
        .filter(entry => typeof entry === 'string' && entry.endsWith('.md'))
        .map(entry => resolve(docsDirectory, entry as string))
    ]
    const missing: string[] = []
    for (const file of markdownFiles) {
      const markdown = readFileSync(file, 'utf8')
      for (const match of markdown.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
        const target = match[1]!.trim().split('#')[0]!
        if (!target || /^(?:https?:|mailto:|\/)/.test(target)) continue
        const decoded = decodeURIComponent(target.replace(/^<|>$/g, ''))
        if (!existsSync(resolve(dirname(file), decoded))) missing.push(`${file}: ${target}`)
      }
    }
    expect(missing).toEqual([])
  })
})
