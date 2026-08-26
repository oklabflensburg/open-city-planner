import type { AuthUser } from '~/types/auth'
import { hasVerwaltungRole } from '~/utils/roles'
import {
  isUiContributionVisible,
  type UiContribution,
  type UiSlotId,
  type UiVisibilityContext
} from '#frontend-module-sdk'

export type UiVisibilityOverrides = Partial<Omit<UiVisibilityContext, 'authenticated'>>

export function useUiContributions<S extends UiSlotId>(slot: S, overrides: UiVisibilityOverrides = {}) {
  const authStore = useAuthStore()
  const runtimeConfig = useRuntimeConfig().public as unknown as {
    frontendModules?: readonly string[]
    frontendUiContributions?: readonly UiContribution[]
  }
  const enabledModules = new Set(runtimeConfig.frontendModules ?? [])
  const contributions = runtimeConfig.frontendUiContributions ?? []

  return computed(() => {
    const context: UiVisibilityContext = {
      authenticated: authStore.authenticated,
      can: overrides.can ?? (permission => resolveHostUiPermission(authStore.user, permission)),
      featureEnabled: overrides.featureEnabled ?? (() => false),
      moduleEnabled: overrides.moduleEnabled ?? (moduleId => enabledModules.has(moduleId))
    }
    return contributions.filter(
      contribution => contribution.slot === slot && isUiContributionVisible(contribution, context)
    ) as unknown as readonly Extract<UiContribution, { slot: S }>[]
  })
}

export function resolveHostUiPermission(user: AuthUser | null, permission: string) {
  if (permission === 'platform.verwaltung') return hasVerwaltungRole(user)
  if (permission === 'platform.superuser') return Boolean(user?.is_superuser)
  return false
}
