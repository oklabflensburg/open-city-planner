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

export interface EmailTemplateListItem {
  key: string
  name: string
  description: string
  category: 'Sicherheit' | 'Konto' | 'Kontakt' | 'Kommunikation / System'
  customized: boolean
  active: boolean
  security_sensitive: boolean
  version: number
  updated_at: string | null
  updated_by: string | null
}

export interface EmailTemplateDetail extends EmailTemplateListItem {
  subject: string
  html_body: string
  text_body: string
  allowed_variables: string[]
  required_variables: string[]
}

export interface EmailTemplatePreview {
  subject: string
  html: string
  text: string
}

export interface EmailCampaignPreview extends EmailTemplatePreview {}

export type EmailCampaignType = 'LEGAL' | 'SERVICE' | 'NEWSLETTER' | 'SYSTEM'
export type EmailCampaignStatus = 'DRAFT' | 'SCHEDULED' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED'
export type EmailRecipientScope = 'ALL_ACTIVE_USERS' | 'VERIFIED_USERS' | 'SUPERUSERS'

export interface EmailCampaign {
  id: string
  internal_name: string
  subject: string
  title: string
  intro: string | null
  content_html: string
  content_text: string
  action_url: string | null
  action_label: string | null
  campaign_type: EmailCampaignType
  status: EmailCampaignStatus
  recipient_scope: EmailRecipientScope
  created_at: string
  updated_at: string
  scheduled_at: string | null
  started_at: string | null
  completed_at: string | null
  recipient_count: number
  sent_count: number
  failed_count: number
  skipped_count: number
  version: number
}

export type EmailCampaignWrite = Pick<EmailCampaign,
  'internal_name' | 'subject' | 'title' | 'intro' | 'content_html' | 'content_text' |
  'action_url' | 'action_label' | 'campaign_type' | 'recipient_scope' | 'scheduled_at' | 'version'
>
