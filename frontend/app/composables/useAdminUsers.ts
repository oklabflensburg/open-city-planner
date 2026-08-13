import type { AdminRole, AdminUser, AdminUserList } from '~/types/admin'

export function useAdminUsers() {
  const authStore = useAuthStore()
  const { request } = useApi()
  const users = ref<AdminUser[]>([])
  const roles = ref<AdminRole[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = 25
  const search = ref('')
  const role = ref('')
  const active = ref<'all' | 'active' | 'inactive'>('all')
  const loading = ref(false)
  const mutationKey = ref('')
  const error = ref('')
  let latestRequest = 0

  async function loadRoles() {
    roles.value = await request<AdminRole[]>('/admin/roles')
  }

  async function loadUsers() {
    const requestId = ++latestRequest
    loading.value = true
    error.value = ''
    try {
      const query = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) })
      if (search.value.trim()) query.set('search', search.value.trim())
      if (role.value) query.set('role', role.value)
      if (active.value !== 'all') query.set('is_active', String(active.value === 'active'))
      const result = await request<AdminUserList>(`/admin/users?${query}`)
      if (requestId === latestRequest) {
        users.value = result.items
        total.value = result.total
      }
    } catch (caught) {
      if (requestId === latestRequest) {
        error.value = caught instanceof Error ? caught.message : 'Benutzer konnten nicht geladen werden.'
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  async function loadUser(userId: string) {
    return await request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`)
  }

  async function assignRole(user: AdminUser, roleName: string) {
    mutationKey.value = `${user.id}:${roleName}`
    try {
      const updated = await request<AdminUser>(
        `/admin/users/${encodeURIComponent(user.id)}/roles/${encodeURIComponent(roleName)}`,
        { method: 'PUT' }
      )
      replaceUser(updated)
      if (user.id === authStore.user?.id) await authStore.refreshUser()
      return updated
    } finally {
      mutationKey.value = ''
    }
  }

  async function removeRole(user: AdminUser, roleName: string) {
    mutationKey.value = `${user.id}:${roleName}`
    try {
      await request(
        `/admin/users/${encodeURIComponent(user.id)}/roles/${encodeURIComponent(roleName)}`,
        { method: 'DELETE' }
      )
      const updated = { ...user, roles: user.roles.filter(item => item !== roleName) }
      replaceUser(updated)
      if (user.id === authStore.user?.id) await authStore.refreshUser()
      return updated
    } finally {
      mutationKey.value = ''
    }
  }

  async function setActive(user: AdminUser, isActive: boolean) {
    mutationKey.value = `${user.id}:status`
    try {
      const updated = await request<AdminUser>(`/admin/users/${encodeURIComponent(user.id)}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive })
      })
      replaceUser(updated)
      return updated
    } finally {
      mutationKey.value = ''
    }
  }

  function replaceUser(user: AdminUser) {
    users.value = users.value.map(item => item.id === user.id ? user : item)
  }

  return {
    users, roles, total, page, pageSize, search, role, active, loading, mutationKey, error,
    loadRoles, loadUsers, loadUser, assignRole, removeRole, setActive
  }
}
