import type { NotificationPriority } from '~/types/notification'

export function formatNotificationTime(value: string, now = new Date()) {
  const date = new Date(value)
  const seconds = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000))
  if (seconds < 60) return 'gerade eben'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `vor ${minutes} Min.`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `vor ${hours} Std.`
  const days = Math.floor(hours / 24)
  if (days < 7) return days === 1 ? 'gestern' : `vor ${days} Tagen`
  return new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function shouldToastNotification(priority: NotificationPriority) {
  return ['SUCCESS', 'ERROR', 'ACTION_REQUIRED'].includes(priority)
}

export function safeNotificationTarget(value: string | null | undefined) {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : null
}
