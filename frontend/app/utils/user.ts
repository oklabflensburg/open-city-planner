import type { AuthUser } from '~/types/auth'

type AvatarUrlOptions = {
  apiBaseUrl?: string
  mediaBaseUrl?: string
}

export function getUserInitials(user: Pick<AuthUser, 'display_name' | 'first_name' | 'last_name' | 'email'> | null | undefined) {
  if (!user) return ''
  const displayName = user.display_name?.trim()
  if (displayName) return initialsFromWords(displayName)
  const names = [user.first_name, user.last_name].map((value) => value?.trim()).filter(Boolean)
  if (names.length) return names.map((value) => value[0]).join('').slice(0, 2).toUpperCase()
  return user.email.trim().slice(0, 1).toUpperCase()
}

export function resolveAvatarUrl(avatarUrl: string | null | undefined, options: AvatarUrlOptions = {}) {
  if (!avatarUrl) return ''
  if (/^blob:/i.test(avatarUrl)) return avatarUrl
  if (/^https?:\/\//i.test(avatarUrl)) return repairLegacyMediaPath(avatarUrl)
  if (options.mediaBaseUrl) {
    const mediaBaseUrl = options.mediaBaseUrl.replace(/\/$/, '').replace(/\/media$/, '')
    return `${mediaBaseUrl}${avatarUrl}`
  }
  if (options.apiBaseUrl && avatarUrl.startsWith('/api/')) {
    try {
      const origin = new URL(options.apiBaseUrl).origin
      return `${origin}${avatarUrl}`
    } catch {
      return avatarUrl
    }
  }
  return avatarUrl
}

function repairLegacyMediaPath(value: string) {
  return value.replace('/media/api/v1/media/avatars/', '/api/v1/media/avatars/')
}

function initialsFromWords(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}
