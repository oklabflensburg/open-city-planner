import type { FrontendModuleUiContribution } from './ui-contract.ts'
import type { FrontendModuleMapContributions } from './map-contract.ts'

export const FRONTEND_HOST_VERSION = '1.0.0'
export const FRONTEND_MODULE_SDK_VERSION = '1.2.0'

export interface FrontendModuleCompatibility {
  host: string
  sdk: string
  backend?: string
}

export interface FrontendModuleRouteContribution {
  path: string
  source: string
}

export interface FrontendModulePublicContributions {
  readonly routes: readonly FrontendModuleRouteContribution[]
  readonly ui: readonly FrontendModuleUiContribution[]
  readonly map: FrontendModuleMapContributions
}

export interface FrontendModuleRequirements {
  modules: Record<string, string>
}

export interface FrontendModuleDefinition {
  schemaVersion: 1
  id: string
  version: string
  backendModuleId?: string
  compatibility: FrontendModuleCompatibility
  layer: string
  requires: FrontendModuleRequirements
  publicContributions: FrontendModulePublicContributions
}

export interface ResolvedFrontendModule extends FrontendModuleDefinition {
  source: string
  layerPath: string
  trustClass: 'first-party'
}
