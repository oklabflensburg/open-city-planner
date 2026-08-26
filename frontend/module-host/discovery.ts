import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { basename, dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import { satisfies, valid, validRange } from 'semver'
import { z } from 'zod'
import {
  FRONTEND_HOST_VERSION,
  FRONTEND_MODULE_SDK_VERSION,
  type FrontendModuleDefinition,
  type ResolvedFrontendModule
} from './contract.ts'
import { createFrontendContributionRegistry } from './ui-registry.ts'
import { createMapExtensionDefinitionRegistry } from './map-definition-registry.ts'
import { MAP_LAYER_GROUPS } from './map-contract.ts'

const moduleId = z.string().regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/).max(63)
const uiVisibility = z.strictObject({
  auth: z.enum(['public', 'authenticated', 'anonymous']).optional(),
  permission: z.string().min(1).optional(),
  feature: z.string().min(1).optional(),
  module: moduleId.optional()
})
const uiContributionBase = {
  id: z.string().min(3),
  priority: z.number().int().min(-1_000_000).max(1_000_000).optional(),
  visibility: uiVisibility.optional()
}
const navigationContribution = z.strictObject({
  ...uiContributionBase,
  slot: z.enum(['navigation.primary', 'navigation.user', 'navigation.admin']),
  label: z.string().min(1),
  to: z.string().startsWith('/'),
  exact: z.boolean().optional()
})
const componentContributionBase = {
  ...uiContributionBase,
  component: z.string().regex(/^[A-Z][A-Za-z0-9]*$/),
  source: z.string().min(1),
  props: z.record(z.string(), z.json()).optional()
}
const headerActionContribution = z.strictObject({
  ...componentContributionBase,
  slot: z.literal('header.actions'),
  accessibleLabel: z.string().min(1)
})
const mapControlContribution = z.strictObject({
  ...componentContributionBase,
  slot: z.literal('map.controls'),
  accessibleLabel: z.string().min(1)
})
const componentContribution = z.strictObject({
  ...componentContributionBase,
  slot: z.enum([
    'sidebar',
    'dashboard.widgets',
    'profile.sections',
    'map.bottomSheet',
    'map.contextMenu'
  ])
})

const route = z.strictObject({
  path: z.string().startsWith('/'),
  source: z.string().min(1)
})
const mapSourceContribution = z.strictObject({
  id: z.string().min(3),
  source: z.record(z.string(), z.json())
})
const mapLayerContribution = z.strictObject({
  id: z.string().min(3),
  sourceId: z.string().min(3),
  layer: z.record(z.string(), z.json()),
  group: z.enum(MAP_LAYER_GROUPS),
  priority: z.number().int().min(-1_000_000).max(1_000_000).optional(),
  visible: z.boolean().optional()
})
const definitionSchema = z.strictObject({
  schemaVersion: z.literal(1),
  id: moduleId,
  version: z.string().min(1),
  backendModuleId: moduleId.optional(),
  compatibility: z.strictObject({
    host: z.string().min(1),
    sdk: z.string().min(1),
    backend: z.string().min(1).optional()
  }),
  layer: z.string().min(1),
  requires: z.strictObject({
    modules: z.record(moduleId, z.string().min(1))
  }),
  publicContributions: z.strictObject({
    routes: z.array(route),
    ui: z.array(z.union([navigationContribution, headerActionContribution, mapControlContribution, componentContribution])).default([]),
    map: z.strictObject({
      sources: z.array(mapSourceContribution).default([]),
      layers: z.array(mapLayerContribution).default([])
    }).default({ sources: [], layers: [] })
  })
})

export interface ResolveFrontendModulesOptions {
  modulesDirectory: string
  appPagesDirectory: string
  enabledModules?: string | readonly string[]
  backendModules?: string
  hostVersion?: string
  sdkVersion?: string
}

export class FrontendModuleError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FrontendModuleError'
  }
}

export function resolveFrontendModules(options: ResolveFrontendModulesOptions): ResolvedFrontendModule[] {
  const available = discoverFrontendModules(options.modulesDirectory)
  const byId = new Map(available.map(module => [module.id, module]))
  const enabledIds = parseEnabledModules(options.enabledModules ?? '')
  const enabled = enabledIds.map((id) => {
    const module = byId.get(id)
    if (!module) {
      throw new FrontendModuleError(`Enabled frontend module "${id}" was not found in ${options.modulesDirectory}.`)
    }
    return module
  })

  validateCompatibility(
    enabled,
    options.hostVersion ?? FRONTEND_HOST_VERSION,
    options.sdkVersion ?? FRONTEND_MODULE_SDK_VERSION,
    options.backendModules
  )
  const ordered = resolveModuleOrder(enabled)
  validateRouteCollisions(ordered, options.appPagesDirectory)
  createFrontendContributionRegistry(ordered, discoverPageRoutes(options.appPagesDirectory))
  createMapExtensionDefinitionRegistry(ordered)
  return ordered
}

export function discoverFrontendModules(modulesDirectory: string): ResolvedFrontendModule[] {
  if (!existsSync(modulesDirectory)) return []
  const discovered: ResolvedFrontendModule[] = []
  const sources = new Map<string, string>()
  const entries = readdirSync(modulesDirectory, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .sort((left, right) => left.name.localeCompare(right.name, 'en'))

  for (const entry of entries) {
    const source = resolve(modulesDirectory, entry.name, 'module.json')
    if (!existsSync(source)) continue
    let raw: unknown
    try {
      raw = JSON.parse(readFileSync(source, 'utf8'))
    } catch (error) {
      throw new FrontendModuleError(`Frontend module definition ${source} is not valid JSON: ${errorName(error)}.`)
    }
    const parsed = definitionSchema.safeParse(raw)
    if (!parsed.success) {
      throw new FrontendModuleError(`Frontend module definition ${source} is invalid: ${parsed.error.issues[0]?.message ?? 'unknown validation error'}.`)
    }
    const definition = parsed.data as unknown as FrontendModuleDefinition
    validateDefinitionVersions(definition, source)
    if (definition.backendModuleId && definition.backendModuleId !== definition.id) {
      throw new FrontendModuleError(`Frontend module "${definition.id}" declares backend module "${definition.backendModuleId}"; full-stack modules must share one stable module ID.`)
    }
    if (definition.compatibility.backend && !definition.backendModuleId) {
      throw new FrontendModuleError(`Frontend module "${definition.id}" declares backend compatibility without a backendModuleId.`)
    }
    const previousSource = sources.get(definition.id)
    if (previousSource) {
      throw new FrontendModuleError(`Duplicate frontend module ID "${definition.id}" in ${previousSource} and ${source}.`)
    }
    sources.set(definition.id, source)
    const moduleRoot = dirname(source)
    const layerPath = safeChildPath(moduleRoot, definition.layer, `layer of frontend module "${definition.id}"`)
    if (!existsSync(layerPath) || !statSync(layerPath).isDirectory()) {
      throw new FrontendModuleError(`Layer for frontend module "${definition.id}" does not exist at ${layerPath}.`)
    }
    validateLayerBoundaries(definition, moduleRoot, layerPath)
    for (const contribution of definition.publicContributions.routes) {
      const routeSource = safeChildPath(moduleRoot, contribution.source, `route source of frontend module "${definition.id}"`)
      if (!existsSync(routeSource) || !statSync(routeSource).isFile()) {
        throw new FrontendModuleError(`Route "${contribution.path}" of frontend module "${definition.id}" has no file at ${routeSource}.`)
      }
    }
    for (const contribution of definition.publicContributions.ui) {
      if (!('source' in contribution)) continue
      const componentSource = safeChildPath(moduleRoot, contribution.source, `component source of UI contribution "${contribution.id}"`)
      const componentsDirectory = resolve(layerPath, 'app/components')
      const sourceFromComponents = relative(componentsDirectory, componentSource)
      if (sourceFromComponents === '..' || sourceFromComponents.startsWith(`..${sep}`)) {
        throw new FrontendModuleError(`UI contribution "${contribution.id}" must point into its own layer app/components directory.`)
      }
      if (!existsSync(componentSource) || !statSync(componentSource).isFile()) {
        throw new FrontendModuleError(`UI contribution "${contribution.id}" has no component file at ${componentSource}.`)
      }
      if (!componentSource.endsWith('.vue') || basename(componentSource, '.vue') !== contribution.component) {
        throw new FrontendModuleError(`UI contribution "${contribution.id}" component name "${contribution.component}" must match its local Vue filename.`)
      }
    }
    validateModuleImports(definition.id, moduleRoot, layerPath)
    discovered.push({ ...definition, source, layerPath })
  }
  return discovered
}

export function parseEnabledModules(value: string | readonly string[]): string[] {
  const raw = typeof value === 'string' ? value.split(',') : [...value]
  const ids = raw.map(item => item.trim()).filter(Boolean)
  const seen = new Set<string>()
  for (const id of ids) {
    if (!moduleId.safeParse(id).success) throw new FrontendModuleError(`Invalid enabled frontend module ID "${id}".`)
    if (seen.has(id)) throw new FrontendModuleError(`Frontend module "${id}" is enabled more than once.`)
    seen.add(id)
  }
  return [...seen].sort((left, right) => left.localeCompare(right, 'en'))
}

function validateCompatibility(
  modules: readonly ResolvedFrontendModule[],
  hostVersion: string,
  sdkVersion: string,
  backendModules: string | undefined
) {
  requireVersion(hostVersion, 'frontend host version')
  requireVersion(sdkVersion, 'frontend module SDK version')
  const backendInventory = backendModules === undefined ? undefined : parseBackendModules(backendModules)
  for (const module of modules) {
    requireCompatible(module.id, 'frontend host', hostVersion, module.compatibility.host)
    requireCompatible(module.id, 'frontend module SDK', sdkVersion, module.compatibility.sdk)
    if (backendInventory && module.backendModuleId) {
      const backendVersion = backendInventory.get(module.backendModuleId)
      if (backendVersion === undefined) {
        throw new FrontendModuleError(`Frontend module "${module.id}" requires enabled backend module "${module.backendModuleId}".`)
      }
      if (module.compatibility.backend && backendVersion !== null) {
        requireCompatible(module.id, 'backend module', backendVersion, module.compatibility.backend)
      }
    }
  }
}

function resolveModuleOrder(modules: readonly ResolvedFrontendModule[]): ResolvedFrontendModule[] {
  const byId = new Map(modules.map(module => [module.id, module]))
  const visiting = new Set<string>()
  const visited = new Set<string>()
  const ordered: ResolvedFrontendModule[] = []
  const visit = (module: ResolvedFrontendModule) => {
    if (visiting.has(module.id)) throw new FrontendModuleError(`Circular frontend module dependency involving "${module.id}".`)
    if (visited.has(module.id)) return
    visiting.add(module.id)
    for (const dependencyId of Object.keys(module.requires.modules).sort((left, right) => left.localeCompare(right, 'en'))) {
      const dependency = byId.get(dependencyId)
      if (!dependency) throw new FrontendModuleError(`Frontend module "${module.id}" requires enabled module "${dependencyId}".`)
      requireCompatible(module.id, `frontend module ${dependencyId}`, dependency.version, module.requires.modules[dependencyId]!)
      visit(dependency)
    }
    visiting.delete(module.id)
    visited.add(module.id)
    ordered.push(module)
  }
  for (const module of [...modules].sort((left, right) => left.id.localeCompare(right.id, 'en'))) visit(module)
  return ordered
}

function validateRouteCollisions(modules: readonly ResolvedFrontendModule[], appPagesDirectory: string) {
  const owners = new Map<string, string>()
  for (const routePath of discoverPageRoutes(appPagesDirectory)) owners.set(routePath, `host pages at ${appPagesDirectory}`)
  for (const module of modules) {
    for (const contribution of module.publicContributions.routes) {
      const routePath = normalizeRoute(contribution.path)
      const owner = owners.get(routePath)
      if (owner) throw new FrontendModuleError(`Route collision for "${routePath}" between ${owner} and frontend module "${module.id}" (${module.source}).`)
      owners.set(routePath, `frontend module "${module.id}" (${module.source})`)
    }
  }
}

function validateLayerBoundaries(
  definition: FrontendModuleDefinition,
  moduleRoot: string,
  layerPath: string
) {
  for (const forbidden of ['app/app.vue', 'app/layouts', 'app/plugins', 'modules', 'server']) {
    if (existsSync(resolve(layerPath, forbidden))) {
      throw new FrontendModuleError(`Frontend module "${definition.id}" may not provide host-owned layer path "${forbidden}" in V1.`)
    }
  }
  const middlewareDirectory = resolve(layerPath, 'app/middleware')
  if (existsSync(middlewareDirectory) && walkFiles(middlewareDirectory).some(file => /\.global\.[cm]?[jt]s$/.test(file))) {
    throw new FrontendModuleError(`Frontend module "${definition.id}" may not register global middleware in V1.`)
  }

  const pagesDirectory = resolve(layerPath, 'app/pages')
  const pageFiles = existsSync(pagesDirectory)
    ? walkFiles(pagesDirectory).filter(file => file.endsWith('.vue'))
    : []
  const declaredSources = new Set<string>()
  for (const contribution of definition.publicContributions.routes) {
    const source = safeChildPath(moduleRoot, contribution.source, `route source of frontend module "${definition.id}"`)
    const sourceFromPages = relative(pagesDirectory, source)
    if (sourceFromPages === '..' || sourceFromPages.startsWith(`..${sep}`)) {
      throw new FrontendModuleError(`Route "${contribution.path}" of frontend module "${definition.id}" must point into its layer app/pages directory.`)
    }
    const derivedRoute = pageRoute(source, pagesDirectory)
    if (normalizeRoute(contribution.path) !== derivedRoute) {
      throw new FrontendModuleError(`Declared route "${contribution.path}" of frontend module "${definition.id}" does not match Nuxt file route "${derivedRoute}".`)
    }
    declaredSources.add(source)
  }
  const undeclared = pageFiles.find(file => !declaredSources.has(file))
  if (undeclared) {
    throw new FrontendModuleError(`Frontend module "${definition.id}" contains undeclared page ${undeclared}.`)
  }
}

export function discoverPageRoutes(pagesDirectory: string): string[] {
  if (!existsSync(pagesDirectory)) return []
  const files = walkFiles(pagesDirectory).filter(file => file.endsWith('.vue'))
  return files.map(file => pageRoute(file, pagesDirectory)).sort((left, right) => left.localeCompare(right, 'en'))
}

function pageRoute(file: string, pagesDirectory: string): string {
  const page = relative(pagesDirectory, file).replaceAll(sep, '/').replace(/\.vue$/, '')
  const segments = page.split('/').filter(segment => segment !== 'index').map((segment) => {
    if (segment.startsWith('[[...') && segment.endsWith(']]')) return `:${segment.slice(5, -2)}(.*)*`
    if (segment.startsWith('[...') && segment.endsWith(']')) return `:${segment.slice(4, -1)}(.*)*`
    if (segment.startsWith('[') && segment.endsWith(']')) return `:${segment.slice(1, -1)}`
    return segment
  })
  return normalizeRoute(`/${segments.join('/')}`)
}

function walkFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name, 'en'))
    .flatMap((entry) => {
      const path = resolve(directory, entry.name)
      return entry.isDirectory() ? walkFiles(path) : [path]
    })
}

function validateModuleImports(moduleId: string, moduleRoot: string, layerPath: string) {
  const sourceFiles = walkFiles(layerPath).filter(file => /\.(?:vue|[cm]?[jt]sx?)$/.test(file))
  const importPattern = /(?:from\s*|import\s*\()\s*['"]([^'"]+)['"]/g
  for (const file of sourceFiles) {
    const contents = readFileSync(file, 'utf8')
    for (const match of contents.matchAll(importPattern)) {
      const specifier = match[1]!
      if (specifier.startsWith('~/') || specifier.startsWith('@/') || specifier.includes('frontend-modules/')) {
        throw new FrontendModuleError(`Frontend module "${moduleId}" imports private host or module internals via "${specifier}" in ${file}.`)
      }
      if (!specifier.startsWith('.')) continue
      const target = resolve(dirname(file), specifier)
      const fromModule = relative(moduleRoot, target)
      if (fromModule === '..' || fromModule.startsWith(`..${sep}`)) {
        throw new FrontendModuleError(`Frontend module "${moduleId}" imports outside its own module through "${specifier}" in ${file}.`)
      }
    }
  }
}

function validateDefinitionVersions(definition: FrontendModuleDefinition, source: string) {
  requireVersion(definition.version, `version in ${source}`)
  requireRange(definition.compatibility.host, `host compatibility in ${source}`)
  requireRange(definition.compatibility.sdk, `SDK compatibility in ${source}`)
  if (definition.compatibility.backend) requireRange(definition.compatibility.backend, `backend compatibility in ${source}`)
  for (const [dependency, range] of Object.entries(definition.requires.modules)) {
    requireRange(range, `dependency ${dependency} in ${source}`)
  }
}

function requireCompatible(moduleId: string, target: string, version: string, range: string) {
  requireRange(range, `${target} compatibility of frontend module ${moduleId}`)
  if (!satisfies(version, range)) throw new FrontendModuleError(`Frontend module "${moduleId}" requires ${target} ${range}, but found ${version}.`)
}

function requireVersion(value: string, label: string) {
  if (!valid(value)) throw new FrontendModuleError(`Invalid full SemVer ${label}: "${value}".`)
}

function requireRange(value: string, label: string) {
  if (!validRange(value)) throw new FrontendModuleError(`Invalid SemVer range for ${label}: "${value}".`)
}

function parseBackendModules(value: string): Map<string, string | null> {
  const modules = new Map<string, string | null>()
  for (const item of value.split(',').map(part => part.trim()).filter(Boolean)) {
    const [id, version, ...rest] = item.split('@')
    if (!id || rest.length || !moduleId.safeParse(id).success) throw new FrontendModuleError(`Invalid backend module inventory entry "${item}".`)
    if (modules.has(id)) throw new FrontendModuleError(`Backend module "${id}" occurs more than once in the build inventory.`)
    if (version) requireVersion(version, `backend module ${id}`)
    modules.set(id, version || null)
  }
  return modules
}

function safeChildPath(parent: string, child: string, label: string): string {
  if (isAbsolute(child)) throw new FrontendModuleError(`The ${label} must be a relative local path.`)
  const result = resolve(parent, child)
  const pathFromParent = relative(parent, result)
  if (!pathFromParent || pathFromParent === '..' || pathFromParent.startsWith(`..${sep}`)) {
    if (!pathFromParent) return result
    throw new FrontendModuleError(`The ${label} must remain inside ${parent}.`)
  }
  return result
}

function normalizeRoute(path: string): string {
  if (path.includes('?') || path.includes('#') || !path.startsWith('/')) throw new FrontendModuleError(`Invalid module route "${path}".`)
  return path === '/' ? path : path.replace(/\/+$/, '')
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : 'unknown error'
}
