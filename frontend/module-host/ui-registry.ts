import type { ResolvedFrontendModule } from './contract.ts'
import {
  DEFAULT_UI_CONTRIBUTION_PRIORITY,
  UI_SLOT_IDS,
  type FrontendModuleUiContribution,
  type UiContribution,
  type UiSlotId,
  type UiVisibilityContext
} from './ui-contract.ts'

const slots = new Set<string>(UI_SLOT_IDS)

export class FrontendContributionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FrontendContributionError'
  }
}

export class DuplicateUiContributionError extends FrontendContributionError {
  constructor(
    id: string,
    first: Pick<UiContribution, 'moduleId' | 'slot'>,
    second: Pick<UiContribution, 'moduleId' | 'slot'>
  ) {
    super(`Duplicate UI contribution "${id}" in slot "${first.slot}" from module "${first.moduleId}" and slot "${second.slot}" from module "${second.moduleId}".`)
    this.name = 'DuplicateUiContributionError'
  }
}

export class FrontendContributionRegistry {
  readonly #knownRoutes: ReadonlySet<string>
  readonly #contributions = new Map<string, UiContribution>()
  #sealed = false

  constructor(knownRoutes: Iterable<string>) {
    this.#knownRoutes = new Set(knownRoutes)
  }

  registrar(moduleId: string, moduleOrder: number) {
    if (!/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(moduleId)) {
      throw new FrontendContributionError(`Invalid owner module ID "${moduleId}".`)
    }
    return {
      register: (contribution: FrontendModuleUiContribution) => this.#register(moduleId, moduleOrder, contribution)
    } as const
  }

  seal() {
    this.#sealed = true
    return this
  }

  get sealed() {
    return this.#sealed
  }

  all(): readonly UiContribution[] {
    if (!this.#sealed) throw new FrontendContributionError('UI contribution registry must be sealed before rendering.')
    return Object.freeze([...this.#contributions.values()].sort(compareUiContributions))
  }

  forSlot(slot: UiSlotId, visibility?: UiVisibilityContext): readonly UiContribution[] {
    if (!slots.has(slot)) throw new FrontendContributionError(`Unknown UI slot "${slot}".`)
    return this.all().filter(contribution => contribution.slot === slot && (!visibility || isUiContributionVisible(contribution, visibility)))
  }

  #register(moduleId: string, moduleOrder: number, contribution: FrontendModuleUiContribution) {
    if (this.#sealed) throw new FrontendContributionError(`Cannot register UI contribution "${contribution.id}" after the registry was sealed.`)
    const bound = deepFreeze({ ...contribution, moduleId, moduleOrder }) as UiContribution
    const previous = this.#contributions.get(bound.id)
    if (previous) throw new DuplicateUiContributionError(bound.id, previous, bound)
    validateContribution(moduleId, contribution, this.#knownRoutes)
    this.#contributions.set(bound.id, bound)
    return bound
  }
}

export function createFrontendContributionRegistry(
  modules: readonly ResolvedFrontendModule[],
  hostRoutes: readonly string[]
) {
  const knownRoutes = [
    ...hostRoutes,
    ...modules.flatMap(module => module.publicContributions.routes.map(route => route.path))
  ]
  const registry = new FrontendContributionRegistry(knownRoutes)
  modules.forEach((module, moduleOrder) => {
    const registrar = registry.registrar(module.id, moduleOrder)
    for (const contribution of module.publicContributions.ui) registrar.register(contribution)
  })
  return registry.seal()
}

export function compareUiContributions(left: UiContribution, right: UiContribution) {
  const priority = (left.priority ?? DEFAULT_UI_CONTRIBUTION_PRIORITY) - (right.priority ?? DEFAULT_UI_CONTRIBUTION_PRIORITY)
  if (priority) return priority
  const moduleOrder = left.moduleOrder - right.moduleOrder
  if (moduleOrder) return moduleOrder
  return left.id.localeCompare(right.id, 'en')
}

export function isUiContributionVisible(contribution: UiContribution, context: UiVisibilityContext) {
  const visibility = contribution.visibility
  if (!visibility) return true
  const auth = visibility.auth ?? 'public'
  if (auth === 'authenticated' && !context.authenticated) return false
  if (auth === 'anonymous' && context.authenticated) return false
  if (visibility.permission && !context.can(visibility.permission)) return false
  if (visibility.feature && !context.featureEnabled(visibility.feature)) return false
  if (visibility.module && !context.moduleEnabled(visibility.module)) return false
  return true
}

function validateContribution(
  moduleId: string,
  contribution: FrontendModuleUiContribution,
  knownRoutes: ReadonlySet<string>
) {
  if (!slots.has(contribution.slot)) throw new FrontendContributionError(`Unknown UI slot "${contribution.slot}" for contribution "${contribution.id}".`)
  if (!contribution.id.startsWith(`${moduleId}.`) || !/^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$/.test(contribution.id)) {
    throw new FrontendContributionError(`UI contribution "${contribution.id}" must use the stable owner prefix "${moduleId}.".`)
  }
  if (contribution.priority !== undefined && (!Number.isSafeInteger(contribution.priority) || Math.abs(contribution.priority) > 1_000_000)) {
    throw new FrontendContributionError(`UI contribution "${contribution.id}" has an invalid priority.`)
  }
  if ('to' in contribution && !knownRoutes.has(normalizeStaticRoute(contribution.to))) {
    throw new FrontendContributionError(`Navigation contribution "${contribution.id}" points to unknown static route "${contribution.to}".`)
  }
  if ((contribution.slot === 'header.actions' || contribution.slot === 'map.controls') && !contribution.accessibleLabel.trim()) {
    throw new FrontendContributionError(`UI control "${contribution.id}" requires an accessible label.`)
  }
}

function normalizeStaticRoute(route: string) {
  if (!route.startsWith('/') || route.includes('?') || route.includes('#') || route.includes(':')) {
    throw new FrontendContributionError(`Navigation route "${route}" must be a static application path.`)
  }
  return route === '/' ? route : route.replace(/\/+$/, '')
}

function deepFreeze<T>(value: T): T {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value
  for (const nested of Object.values(value)) deepFreeze(nested)
  return Object.freeze(value)
}
