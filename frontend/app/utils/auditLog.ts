export type AuditTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

const ACTION_LABELS: Record<string, string> = {
  USER_ROLE_ASSIGNED: 'Rolle zugewiesen',
  USER_ROLE_REMOVED: 'Rolle entfernt',
  USER_ACTIVATED: 'Konto aktiviert',
  USER_DEACTIVATED: 'Konto deaktiviert',
  ACCOUNT_DEACTIVATED: 'Konto selbst deaktiviert',
  ACCOUNT_DELETED: 'Konto selbst gelöscht',
  LOGIN_BLOCKED: 'Anmeldung blockiert',
  USER_SUPERUSER_GRANTED_DIRECT: 'Superuser-Status zugewiesen',
  REFRESH_TOKEN_REUSE_DETECTED: 'Token-Wiederverwendung erkannt',
  FLENSBURG_STATISTICS_SYNC: 'Flensburg-Statistik synchronisiert',
  MASTODON_STATUS_PUBLISHED: 'Mastodon-Status veröffentlicht',
  MASTODON_PUBLICATION_FAILED: 'Mastodon-Veröffentlichung fehlgeschlagen',
  MASTODON_PUBLICATION_RETRY_REQUESTED: 'Mastodon-Wiederholung angefordert',
  MASTODON_PUBLICATION_APPROVED: 'Mastodon-Post freigegeben',
  MASTODON_PUBLICATION_CANCELLED: 'Mastodon-Post verworfen',
  SOCIAL_PUBLISHING_SETTINGS_UPDATED: 'Social-Einstellungen geändert',
  OAUTH_LOGIN_SUCCESS: 'Externe Anmeldung erfolgreich',
  OAUTH_LOGIN_FAILED: 'Externe Anmeldung fehlgeschlagen',
  OAUTH_ACCOUNT_LINKED: 'Externes Konto verknüpft',
  OAUTH_ACCOUNT_LINK_FAILED: 'Kontoverknüpfung fehlgeschlagen',
  OAUTH_ACCOUNT_UNLINKED: 'Externes Konto getrennt'
}

export function auditActionLabel(action: string) {
  return ACTION_LABELS[action] || action.replaceAll('_', ' ')
}

export function auditActionTone(action: string): AuditTone {
  if (action === 'LOGIN_BLOCKED') return 'warning'
  if (action.includes('DEACTIVATED') || action.includes('DELETE') || action.includes('REUSE')) return 'danger'
  if (action.includes('ACTIVATED') || action.includes('ASSIGNED') || action.includes('CREATE')) return 'success'
  if (action.includes('REMOVED')) return 'warning'
  if (action.includes('AUTH') || action.includes('LOGIN')) return 'info'
  return 'neutral'
}

export function blockedLoginDetailRows(details: Record<string, unknown>) {
  if (!details.reason && !details.provider) return []
  const reason = {
    SELF_DEACTIVATED: 'Selbst deaktiviert',
    ADMIN_DEACTIVATED: 'Konto deaktiviert'
  }[String(details.reason)] || 'Konto deaktiviert'
  const provider = {
    password: 'E-Mail / Passwort',
    google: 'Google',
    github: 'GitHub',
    mastodon: 'Mastodon'
  }[String(details.provider)] || String(details.provider || 'Unbekannt')
  return [
    { label: 'Grund', value: reason },
    { label: 'Anmeldemethode', value: provider }
  ]
}

export function formatAuditDate(value: string) {
  return new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))
}

export function auditChangeRows(details: Record<string, unknown>) {
  const changes = isRecord(details.changes) ? details.changes : null
  if (changes) return Object.entries(changes).flatMap(([field, value]) => isRecord(value) && ('before' in value || 'after' in value)
    ? [{ field, before: value.before, after: value.after }]
    : [])
  const before = details.before
  const after = details.after
  if (isRecord(before) && isRecord(after)) {
    return [...new Set([...Object.keys(before), ...Object.keys(after)])]
      .map(field => ({ field, before: before[field], after: after[field] }))
  }
  return []
}

export function displayAuditValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
