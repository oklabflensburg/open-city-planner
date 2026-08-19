export type NotificationCategory = 'GIS' | 'DATA' | 'OSM' | 'SOCIAL' | 'ACCOUNT' | 'ADMIN' | 'SYSTEM'
export type NotificationPriority = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR' | 'ACTION_REQUIRED'

export interface AppNotification {
  id: string
  event_type: string
  category: NotificationCategory
  priority: NotificationPriority
  title: string
  message: string
  resource_type: string | null
  resource_id: string | null
  resource_slug: string | null
  action_url: string | null
  action_label: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
  metadata: Record<string, unknown>
}

export interface NotificationPage {
  items: AppNotification[]
  total: number
  unread_count: number
  page: number
  page_size: number
  pages: number
}

export interface NotificationPreferences {
  in_app_enabled: boolean
  notify_gis: boolean
  notify_osm: boolean
  notify_area_updates: boolean
  notify_social: boolean
  notify_account: boolean
  notify_system: boolean
  email_enabled: boolean
  email_notify_gis: boolean
  email_notify_osm: boolean
  email_notify_area_updates: boolean
  email_notify_social: boolean
  email_notify_system: boolean
  newsletter_enabled: boolean
  updated_at: string | null
}

export interface NotificationSubscription {
  resource_type: 'POLYGON' | 'AREA'
  resource_id: string
  event_types: string[]
  created_at: string
}

export interface AppToast {
  id: string
  title: string
  message?: string
  priority: NotificationPriority
}
