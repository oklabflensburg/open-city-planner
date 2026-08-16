export interface AdminRole {
  name: string
  description: string
}

export interface AdminUser {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_verified: boolean
  is_superuser: boolean
  roles: string[]
  created_at: string
  last_login_at: string | null
  oauth_providers: string[]
}

export interface AdminUserList {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface AuditLogActor {
  id: string
  display_name: string | null
  email: string
}

export interface AuditLogResource {
  type: 'USER' | 'SYSTEM' | string
  id: string | null
  label: string
}

export interface AuditLogItem {
  id: string
  created_at: string
  action: string
  actor: AuditLogActor | null
  resource: AuditLogResource
  summary: string
  details: Record<string, unknown>
}

export interface AuditLogPage {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
  pages: number
  available_actions: string[]
}

export interface AuditLogFilters {
  search: string
  action: string
  userId: string
  dateFrom: string
  dateTo: string
  page: number
  pageSize: number
}
