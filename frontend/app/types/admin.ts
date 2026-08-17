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

export interface MastodonAdminStatus {
  enabled: boolean
  configured: boolean
  reachable: boolean | null
  account: string
  account_url: string
  area_updates_enabled: boolean
  dry_run: boolean
  visibility: string
  pending: number
  failed: number
  published: number
  last_publication_at: string | null
  verification_error: string | null
  approval_mode: 'AUTOMATIC' | 'MANUAL' | 'DRY_RUN'
  screenshots_required: boolean
}

export type SocialPublicationStatus = 'PENDING_APPROVAL' | 'PENDING' | 'PROCESSING' | 'PUBLISHED' | 'FAILED' | 'CANCELLED' | 'DRY_RUN'

export interface SocialPublicationItem {
  id: string
  created_at: string
  event_type: string
  resource_type: string
  resource_id: string | null
  resource_name: string
  resource_slug: string | null
  status: SocialPublicationStatus
  attempt_count: number
  next_attempt_at: string
  published_at: string | null
  last_error: string | null
  remote_url: string | null
  changed_fields: string[]
  dry_run: boolean
  screenshot_ready: boolean
  screenshot_target_url: string | null
  screenshot_alt_text: string | null
}

export interface SocialPublicationPage {
  items: SocialPublicationItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SocialEventDefinition {
  event_type: string
  topic: string
  topic_label: string
  label: string
  description: string
  default_enabled: boolean
}

export interface SocialPublishingSettings {
  enabled: boolean
  approval_mode: 'AUTOMATIC' | 'MANUAL' | 'DRY_RUN'
  default_visibility: 'public' | 'unlisted' | 'private'
  language: 'de'
  debounce_seconds: number
  default_hashtags: string[]
  enabled_events: string[]
  screenshot_viewport: 'LANDSCAPE_16_9' | 'LANDSCAPE_OG' | 'SQUARE'
  screenshot_show_map: boolean
  screenshot_show_facts: boolean
  screenshot_show_pois: boolean
  screenshot_show_branding: boolean
  polygon_osm_adoption_link_target: 'DETAIL_PAGE' | 'GIS'
  screenshots_required: boolean
  registry: SocialEventDefinition[]
  updated_at: string
}

export type SocialPublishingSettingsPatch = Partial<Pick<SocialPublishingSettings,
  | 'enabled'
  | 'approval_mode'
  | 'default_visibility'
  | 'language'
  | 'debounce_seconds'
  | 'default_hashtags'
  | 'enabled_events'
  | 'screenshot_viewport'
  | 'screenshot_show_map'
  | 'screenshot_show_facts'
  | 'screenshot_show_pois'
  | 'screenshot_show_branding'
  | 'polygon_osm_adoption_link_target'
>>

export interface SocialPublicationPreview {
  id: string
  text: string
  target_url: string
  target_label: string
  event_type: string
  resource_name: string
  hashtags: string[]
  screenshot_ready: boolean
  screenshot_url: string | null
  alt_text: string
}
