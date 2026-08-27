import type { BoundNavigationContribution } from '#frontend-module-sdk'

export type NavigationItem = {
  id: string
  label: string
  to: string
  priority: number
  moduleOrder: number
  exact?: boolean
}

export const hostPrimaryNavigation = [
  { label: 'Karte', to: '/karte' },
  { label: 'Über das Projekt', to: '/ueber-das-projekt' },
  { label: 'Dokumentation', to: '/dokumentation' }
] as const

export const hostLegalNavigation = [
  { label: 'Impressum', to: '/impressum' },
  { label: 'Datenschutz', to: '/datenschutz' }
] as const

export function useSiteNavigation() {
  const primaryContributions = useUiContributions('navigation.primary')
  const userContributions = useUiContributions('navigation.user')
  const adminContributions = useUiContributions('navigation.admin')

  return {
    primaryNavigation: computed(() => composeNavigation(hostPrimaryNavigation, primaryContributions.value)),
    legalNavigation: composeNavigation(hostLegalNavigation),
    userNavigation: computed(() => composeNavigation([], userContributions.value)),
    adminNavigation: computed(() => composeNavigation([], adminContributions.value))
  }
}

export function composeNavigation(
  hostItems: readonly { label: string, to: string }[],
  moduleItems: readonly BoundNavigationContribution[] = []
) {
  const host = hostItems.map((item, index): NavigationItem => ({
    id: `host.${item.to === '/' ? 'home' : item.to.slice(1).replaceAll('/', '.')}`,
    ...item,
    priority: (index + 1) * 100,
    moduleOrder: -1
  }))
  const modules = moduleItems.map((item): NavigationItem => ({
    id: item.id,
    label: item.label,
    to: item.to,
    priority: item.priority ?? 100,
    moduleOrder: item.moduleOrder,
    exact: item.exact
  }))
  return sortNavigationItems([...host, ...modules])
}

export function sortNavigationItems(items: readonly NavigationItem[]) {
  return [...items].sort((left, right) =>
    left.priority - right.priority
    || left.moduleOrder - right.moduleOrder
    || left.id.localeCompare(right.id, 'en')
  )
}
