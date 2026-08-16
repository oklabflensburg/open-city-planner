import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { buildAuditLogQuery } from '../app/composables/useAuditLog'
import { auditChangeRows } from '../app/utils/auditLog'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('superuser audit log', () => {
  it('is linked only behind the superuser guard and excluded from indexing', () => {
    const header = appFile('components/layout/AppHeader.vue')
    const page = appFile('pages/admin/audit-log.vue')
    expect(header).toContain("{ label: 'Auditlog', to: '/admin/audit-log' }")
    expect(header.indexOf("authStore.user?.is_superuser ?")).toBeLessThan(header.indexOf("to: '/admin/audit-log'"))
    expect(page).toContain("middleware: 'superuser'")
    expect(page).toContain("robots: 'noindex,nofollow'")
    expect(page).toContain('openGraph: false')
    expect(page).toContain('structuredData: false')
  })

  it('builds paginated API filters with timezone-aware day boundaries', () => {
    const query = buildAuditLogQuery({
      search: ' Erika ', action: 'USER_ACTIVATED', userId: 'actor-id',
      dateFrom: '2026-08-01', dateTo: '2026-08-16', page: 3, pageSize: 25
    })
    expect(query.get('page')).toBe('3')
    expect(query.get('page_size')).toBe('25')
    expect(query.get('search')).toBe('Erika')
    expect(query.get('action')).toBe('USER_ACTIVATED')
    expect(query.get('user_id')).toBe('actor-id')
    expect(new Date(query.get('date_from')!).toString()).not.toBe('Invalid Date')
    expect(new Date(query.get('date_to')!).getTime()).toBeGreaterThan(new Date(query.get('date_from')!).getTime())
  })

  it('provides URL-synchronized filters, pagination and resilient states', () => {
    const page = appFile('pages/admin/audit-log.vue')
    expect(page).toContain('router.replace({ query: nextQuery })')
    expect(page).toContain('setTimeout(() => { void commitFilters() }, 400)')
    expect(page).toContain('Keine Audit-Ereignisse gefunden')
    expect(page).toContain('Auditlog konnte nicht geladen werden')
    expect(page).toContain('Erneut versuchen')
    expect(page).toContain('Seite {{ filters.page }} von {{ pages }}')
  })

  it('renders mobile cards, a desktop table and read-only modal details', () => {
    const page = appFile('pages/admin/audit-log.vue')
    const list = appFile('components/admin/AuditLogList.vue')
    const modal = appFile('components/admin/AuditLogDetailModal.vue')
    expect(page).toContain('<AuditLogList')
    expect(page).toContain('<AuditLogDetailModal')
    expect(page).not.toContain('<AdminAuditLog')
    expect(list).toContain('lg:hidden')
    expect(list).toContain('overflow-hidden lg:block')
    expect(list).toContain('<ul')
    expect(list).toContain('table-fixed')
    expect(list).not.toContain('min-w-[960px]')
    expect(list).toContain('[overflow-wrap:anywhere]')
    expect(list).toContain('<table')
    expect(modal).toContain('<AppModal')
    expect(modal).toContain('JSON.stringify(item.details, null, 2)')
    expect(modal).toContain('Änderungen')
    expect(modal).toContain('sm:hidden')
    expect(`${list}${modal}`).not.toContain('window.confirm')
    expect(`${list}${modal}`).not.toContain('method:')
  })

  it('normalizes before/after metadata into change rows', () => {
    expect(auditChangeRows({ before: { role: null }, after: { role: 'VERWALTUNG' } })).toEqual([
      { field: 'role', before: null, after: 'VERWALTUNG' }
    ])
  })
})
