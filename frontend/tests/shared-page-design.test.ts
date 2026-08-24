import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('shared content page design', () => {
  it('provides one responsive content shell with reading, content and wide widths', () => {
    const shell = appFile('components/layout/ContentPageShell.vue')
    expect(shell).toContain('<PageHeader')
    expect(shell).toContain('<slot name="aside"')
    expect(shell).toContain("reading: 'max-w-4xl'")
    expect(shell).toContain("content: 'max-w-6xl'")
    expect(shell).toContain("wide: 'max-w-7xl'")
    expect(shell).toContain('px-4')
    expect(shell).toContain('sm:px-6')
    expect(shell).toContain('lg:px-8')
  })

  it('renders semantic shared breadcrumbs and a single page heading', () => {
    const breadcrumbs = appFile('components/layout/PageBreadcrumbs.vue')
    const header = appFile('components/layout/PageHeader.vue')
    expect(breadcrumbs).toContain('aria-label="Breadcrumb"')
    expect(breadcrumbs).toContain('aria-current')
    expect(header.match(/<h1/g)).toHaveLength(1)
    expect(header).toContain('<PageBreadcrumbs')
    expect(header).toContain('<slot name="actions"')
  })

  it('uses shared sections, cards, form fields, buttons and status badges', () => {
    expect(appFile('components/ui/ContentSection.vue')).toContain('text-xl font-bold')
    expect(appFile('components/ui/Card.vue')).toContain('rounded-2xl border border-slate-200/80 bg-white shadow-sm')
    expect(appFile('components/auth/FormField.vue')).toContain('rounded-xl border border-slate-300')
    expect(appFile('components/ui/Button.vue')).toContain("'primary' | 'secondary' | 'ghost' | 'danger'")
    expect(appFile('components/docs/DocsRoleBadge.vue')).toContain('<StatusBadge')
  })

  it('builds the about page from shared components and real project capabilities', () => {
    const page = appFile('pages/ueber-das-projekt.vue')
    expect(page).toContain('<ContentPageShell')
    expect(page).toContain('<ContentSection title="Was ist Stadtplaner?"')
    expect(page).toContain('OpenStreetMap')
    expect(page).toContain('Nuxt 4 · Vue 3')
    expect(page).toContain('to="/dokumentation"')
    expect(page).toContain('to="/karte"')
    expect(page).toContain('buildWebPageStructuredData')
  })

  it('keeps documentation navigation exclusive while sharing the page header', () => {
    const docs = appFile('components/docs/DocsLayout.vue')
    expect(docs).toContain('<DocsSidebar')
    expect(docs).toContain('<PageHeader')
    for (const page of ['pages/ueber-das-projekt.vue', 'pages/login.vue', 'pages/profil/index.vue']) {
      expect(appFile(page)).not.toContain('DocsSidebar')
    }
  })

  it('places all auth flows in the shared focused page shell', () => {
    expect(appFile('components/auth/AuthPageShell.vue')).toContain('<ContentPageShell')
    for (const page of ['login', 'registrieren', 'passwort-vergessen', 'passwort-zuruecksetzen', 'email-bestaetigen']) {
      expect(appFile(`pages/${page}.vue`)).toContain('<AuthPageShell')
      expect(appFile(`pages/${page}.vue`)).toContain("robots: 'noindex,nofollow'")
    }
  })

  it('migrates profile, owned polygons and supporting content pages', () => {
    for (const page of ['pages/profil/index.vue', 'pages/profil/sicherheit.vue', 'pages/meine-flaechen.vue', 'pages/kontakt.vue', 'pages/open-data.vue', 'pages/verwaltung/kennzahlen.vue']) {
      expect(appFile(page)).toContain('<ContentPageShell')
    }
    expect(appFile('pages/meine-flaechen.vue')).toContain('Flächen konnten nicht geladen werden.')
    expect(appFile('pages/meine-flaechen.vue')).toContain('Noch keine eigenen Flächen')
  })

  it('keeps GIS pages specialized but shares their header and form tokens', () => {
    expect(appFile('pages/flaechen/neu.vue')).toContain('<ContentPageShell')
    expect(appFile('pages/flaechen/neu.vue')).toContain('<PolygonCreateMap')
    expect(appFile('pages/flaechen/[slug].vue')).toContain('<PageBreadcrumbs')
    expect(appFile('pages/flaechen/[slug].vue')).toContain('<PolygonDetailMap')
    expect(appFile('pages/karte.vue')).toContain('<AppShell')
  })

  it('keeps legal pages in the reading shell without public SEO metadata', () => {
    expect(appFile('components/legal/LegalPageLayout.vue')).toContain('max-width="reading"')
    for (const page of ['impressum', 'datenschutz']) {
      const source = appFile(`pages/${page}.vue`)
      expect(source).toContain("robots: 'noindex,follow'")
      expect(source).toContain('openGraph: false')
      expect(source).toContain('twitter: false')
      expect(source).toContain('structuredData: false')
    }
  })

  it('retains one full-width application header and footer around page content', () => {
    const layout = appFile('layouts/default.vue')
    expect(layout).toContain('<AppHeader')
    expect(layout).toContain('<AppFooter')
    expect(appFile('components/layout/AppHeader.vue')).toContain('route.path.startsWith(`${path}/`)')
  })
})
