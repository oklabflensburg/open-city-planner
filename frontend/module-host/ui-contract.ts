export const UI_SLOT_IDS = [
  'navigation.primary',
  'navigation.user',
  'navigation.admin',
  'header.actions',
  'sidebar',
  'dashboard.widgets',
  'profile.sections',
  'map.controls',
  'map.layers',
  'map.selection',
  'map.bottomSheet',
  'map.contextMenu'
] as const

export type UiSlotId = typeof UI_SLOT_IDS[number]
export type NavigationUiSlotId = Extract<UiSlotId, `navigation.${string}`>
export type ComponentUiSlotId = Exclude<UiSlotId, NavigationUiSlotId>
export type UiAuthVisibility = 'public' | 'authenticated' | 'anonymous'

export type JsonSafeValue =
  | string
  | number
  | boolean
  | null
  | readonly JsonSafeValue[]
  | { readonly [key: string]: JsonSafeValue }

export interface UiVisibilityRule {
  readonly auth?: UiAuthVisibility
  readonly permission?: string
  readonly feature?: string
  readonly module?: string
}

interface FrontendModuleUiContributionBase {
  readonly id: string
  readonly priority?: number
  readonly visibility?: UiVisibilityRule
}

export interface NavigationContribution extends FrontendModuleUiContributionBase {
  readonly slot: NavigationUiSlotId
  readonly label: string
  readonly to: string
  readonly exact?: boolean
}

interface ComponentContributionBase extends FrontendModuleUiContributionBase {
  readonly slot: ComponentUiSlotId
  readonly component: string
  readonly source: string
  readonly props?: Readonly<Record<string, JsonSafeValue>>
}

export interface HeaderActionContribution extends ComponentContributionBase {
  readonly slot: 'header.actions'
  readonly accessibleLabel: string
}

export interface MapUiControlContribution extends ComponentContributionBase {
  readonly slot: 'map.controls'
  readonly accessibleLabel: string
}

export interface GenericComponentContribution extends ComponentContributionBase {
  readonly slot: Exclude<ComponentUiSlotId, 'header.actions' | 'map.controls'>
}

export type FrontendModuleUiContribution =
  | NavigationContribution
  | HeaderActionContribution
  | MapUiControlContribution
  | GenericComponentContribution

export type UiContribution = FrontendModuleUiContribution & {
  readonly moduleId: string
  readonly moduleOrder: number
}

export type BoundNavigationContribution = Extract<UiContribution, { slot: NavigationUiSlotId }>
export type BoundComponentContribution = Extract<UiContribution, { slot: ComponentUiSlotId }>

export interface UiVisibilityContext {
  readonly authenticated: boolean
  readonly can: (permission: string) => boolean
  readonly featureEnabled: (feature: string) => boolean
  readonly moduleEnabled: (moduleId: string) => boolean
}

export const DEFAULT_UI_CONTRIBUTION_PRIORITY = 100
