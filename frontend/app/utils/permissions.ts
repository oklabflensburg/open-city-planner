import type { AuthUser } from '~/types/auth'

export function hasPermissionSnapshot(user: AuthUser | null, permission: string) {
  return Boolean(user?.permissions?.includes(permission))
}
