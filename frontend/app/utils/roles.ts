import type { AuthUser } from '~/types/auth'

export function hasVerwaltungRole(user: Pick<AuthUser, 'is_superuser' | 'roles'> | null | undefined) {
  return !!user?.is_superuser || !!user?.roles?.some(role => role.trim().toUpperCase() === 'VERWALTUNG')
}
