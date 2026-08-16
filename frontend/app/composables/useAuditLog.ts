import type { AdminUser, AdminUserList, AuditLogFilters, AuditLogItem, AuditLogPage } from '~/types/admin'

export function buildAuditLogQuery(filters: AuditLogFilters) {
  const query = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
  if (filters.search.trim()) query.set('search', filters.search.trim())
  if (filters.action) query.set('action', filters.action)
  if (filters.userId) query.set('user_id', filters.userId)
  if (filters.dateFrom) query.set('date_from', dateBoundary(filters.dateFrom, false))
  if (filters.dateTo) query.set('date_to', dateBoundary(filters.dateTo, true))
  return query
}

function dateBoundary(value: string, endOfDay: boolean) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year!, month! - 1, day!, endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0, endOfDay ? 999 : 0).toISOString()
}

export function useAuditLog() {
  const { request } = useApi()
  const items = ref<AuditLogItem[]>([])
  const actors = ref<AdminUser[]>([])
  const availableActions = ref<string[]>([])
  const total = ref(0)
  const pages = ref(1)
  const filters = reactive<AuditLogFilters>({ search: '', action: '', userId: '', dateFrom: '', dateTo: '', page: 1, pageSize: 50 })
  const loading = ref(false)
  const error = ref('')
  let latestRequest = 0

  async function load() {
    const requestId = ++latestRequest
    loading.value = true
    error.value = ''
    try {
      const result = await request<AuditLogPage>(`/admin/audit-logs?${buildAuditLogQuery(filters)}`)
      if (requestId !== latestRequest) return
      items.value = result.items
      total.value = result.total
      pages.value = result.pages
      availableActions.value = result.available_actions
    } catch (caught) {
      if (requestId === latestRequest) error.value = caught instanceof Error ? caught.message : 'Auditlog konnte nicht geladen werden.'
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  async function loadActors() {
    const result = await request<AdminUserList>('/admin/users?page=1&page_size=100')
    actors.value = result.items
  }

  function resetFilters() {
    Object.assign(filters, { search: '', action: '', userId: '', dateFrom: '', dateTo: '', page: 1, pageSize: 50 })
  }

  return { items, actors, availableActions, total, pages, filters, loading, error, load, loadActors, resetFilters }
}
