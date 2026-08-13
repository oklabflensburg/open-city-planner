import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('superuser user administration', () => {
  it('shows the navigation link only behind the superuser flag', () => {
    const header = appFile('components/layout/AppHeader.vue')
    expect(header).toContain("authStore.user?.is_superuser ? [{ label: 'Administration'")
  })

  it('protects the page, disables indexing and uses the shared content design', () => {
    const page = appFile('pages/admin/benutzer.vue')
    expect(page).toContain("middleware: 'superuser'")
    expect(page).toContain('<ContentPageShell')
    expect(page).toContain("robots: 'noindex,nofollow'")
    expect(page).toContain('openGraph: false')
    expect(page).toContain('structuredData: false')
  })

  it('provides debounced search, server filters and pagination', () => {
    const page = appFile('pages/admin/benutzer.vue')
    const composable = appFile('composables/useAdminUsers.ts')
    expect(page).toContain('setTimeout(loadUsers, 400)')
    expect(composable).toContain("query.set('search'")
    expect(composable).toContain("query.set('role'")
    expect(composable).toContain("query.set('is_active'")
    expect(composable).toContain('page_size')
  })

  it('renders desktop table, mobile cards and accessible management dialog', () => {
    const list = appFile('components/admin/AdminUserList.vue')
    const dialog = appFile('components/admin/AdminUserDialog.vue')
    expect(list).toContain('md:hidden')
    expect(list).toContain('hidden overflow-hidden md:block')
    expect(list).toContain('<UserAvatar')
    expect(list).toContain('SUPERUSER')
    expect(dialog).toContain('role="dialog"')
    expect(dialog).toContain('aria-modal="true"')
    expect(dialog).toContain("event.key === 'Escape'")
    expect(dialog).not.toContain('is_superuser =')
  })

  it('uses explicit role endpoints and only updates state after success', () => {
    const composable = appFile('composables/useAdminUsers.ts')
    expect(composable).toContain("{ method: 'PUT' }")
    expect(composable).toContain("{ method: 'DELETE' }")
    expect(composable.indexOf('await request(\n        `/admin/users/${encodeURIComponent(user.id)}/roles')).toBeLessThan(composable.indexOf('const updated = { ...user, roles:'))
    expect(composable).toContain('await authStore.refreshUser()')
  })

  it('does not add the private route to the sitemap', () => {
    const sitemap = readFileSync(fileURLToPath(new URL('../server/routes/sitemap.xml.ts', import.meta.url)), 'utf8')
    expect(sitemap).not.toContain('/admin/benutzer')
  })
})
