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
