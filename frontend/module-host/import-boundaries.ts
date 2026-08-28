import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

export type ArchitectureViolation = {
  rule: 'ARCH-FE-HOST-001' | 'ARCH-FE-MODULE-001'
  source: string
  target: string
  line: number
  reason?: ModuleImportViolation['reason']
}

type BaselineEntry = {
  rule: string
  source: string
  target: string
  tracking_issue: string
  reason: string
}

type ScanOptions = {
  repositoryRoot: string
  frontendRoot?: string
  modulesDirectories?: readonly string[]
  rulesFile?: string
  baselineFile?: string
}

export type ModuleImportViolation = {
  source: string
  target: string
  line: number
  reason: 'private-host-import' | 'private-host-auto-import' | 'module-boundary-escape'
}

const sourceExtension = /\.(?:vue|[cm]?[jt]sx?)$/
const moduleOwnedHostStoreFiles = new Set(['analysisAreas.ts'])
const privateHostComposableFiles = ['useApi.ts', 'useMapSelection.ts']
let cachedPrivateHostAutoImportNames: ReadonlySet<string> | undefined

export function scanFrontendArchitecture(options: ScanOptions): ArchitectureViolation[] {
  const repositoryRoot = resolve(options.repositoryRoot)
  const frontendRoot = resolve(options.frontendRoot ?? resolve(repositoryRoot, 'frontend'))
  const moduleDirectories = options.modulesDirectories?.length
    ? options.modulesDirectories.map(directory => resolve(directory))
    : [resolve(frontendRoot, 'frontend-modules')]
  const moduleEntries = moduleDirectories.flatMap(modulesRoot => existsSync(modulesRoot)
    ? readdirSync(modulesRoot, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .map(entry => ({ id: entry.name, root: resolve(modulesRoot, entry.name) }))
    : [])
  const moduleIds = [...new Set(moduleEntries.map(entry => entry.id))]
  const violations: ArchitectureViolation[] = []

  for (const module of moduleEntries) {
    for (const item of scanModuleImportBoundaries(module.root)) {
      violations.push({ ...makeViolation(repositoryRoot, 'ARCH-FE-MODULE-001', item.source, {
        specifier: item.target,
        line: item.line
      }), reason: item.reason })
    }
  }

  const hostSources = [
    ...walkSourceFiles(resolve(frontendRoot, 'module-host')),
    ...walkSourceFiles(resolve(frontendRoot, 'app')),
    resolve(frontendRoot, 'nuxt.config.ts')
  ].filter((source, index, all) => existsSync(source) && all.indexOf(source) === index)
  for (const source of hostSources) {
    for (const imported of extractImports(source)) {
      if (moduleDirectories.some(modulesRoot => resolvesInside(imported.specifier, source, frontendRoot, modulesRoot))) {
        violations.push(makeViolation(repositoryRoot, 'ARCH-FE-HOST-001', source, imported))
      }
    }
    for (const literal of extractStringLiterals(source)) {
      if (moduleIds.includes(literal.value)) {
        violations.push(makeViolation(
          repositoryRoot,
          'ARCH-FE-HOST-001',
          source,
          { specifier: literal.value, line: literal.line }
        ))
      }
    }
  }

  return unique(violations).sort((left, right) =>
    left.source.localeCompare(right.source, 'en') || left.line - right.line || left.rule.localeCompare(right.rule, 'en')
  )
}

export function scanModuleImportBoundaries(moduleRoot: string, sourceRoot = moduleRoot): ModuleImportViolation[] {
  const resolvedModuleRoot = resolve(moduleRoot)
  const violations: ModuleImportViolation[] = []
  const privateHostAutoImports = privateHostAutoImportNames()
  for (const source of walkSourceFiles(resolve(sourceRoot))) {
    for (const imported of extractImports(source)) {
      if (imported.specifier.startsWith('~/') || imported.specifier.startsWith('@/') || imported.specifier.includes('frontend-modules/')) {
        violations.push({ source, target: imported.specifier, line: imported.line, reason: 'private-host-import' })
        continue
      }
      if (!imported.specifier.startsWith('.')) continue
      const target = resolve(dirname(source), imported.specifier)
      if (!isInside(resolvedModuleRoot, target)) {
        violations.push({ source, target: imported.specifier, line: imported.line, reason: 'module-boundary-escape' })
      }
    }
    for (const called of extractUnboundCalls(source, privateHostAutoImports)) {
      violations.push({ source, target: called.name, line: called.line, reason: 'private-host-auto-import' })
    }
  }
  return violations
}

function privateHostAutoImportNames(): ReadonlySet<string> {
  if (cachedPrivateHostAutoImportNames) return cachedPrivateHostAutoImportNames

  const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
  const storesDirectory = resolve(frontendRoot, 'app/stores')
  const sources = [
    ...(existsSync(storesDirectory)
      ? readdirSync(storesDirectory, { withFileTypes: true })
          .filter(entry => entry.isFile() && sourceExtension.test(entry.name) && !moduleOwnedHostStoreFiles.has(entry.name))
          .map(entry => resolve(storesDirectory, entry.name))
      : []),
    ...privateHostComposableFiles.map(file => resolve(frontendRoot, 'app/composables', file)).filter(existsSync)
  ]
  const names = new Set(sources.flatMap(extractExportedValueNames))
  // Keep detecting the previously used singular spelling if it reappears.
  names.add('useNotificationStore')
  cachedPrivateHostAutoImportNames = names
  return cachedPrivateHostAutoImportNames
}

function extractExportedValueNames(source: string): string[] {
  const file = ts.createSourceFile(source, readFileSync(source, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const names = new Set<string>()
  for (const statement of file.statements) {
    const modifiers = ts.canHaveModifiers(statement) ? ts.getModifiers(statement) : undefined
    if (!modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword)) continue
    if (ts.isFunctionDeclaration(statement) && statement.name) names.add(statement.name.text)
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) collectBindingNames(declaration.name, names)
    }
  }
  return [...names]
}

function collectBindingNames(name: ts.BindingName, names: Set<string>) {
  if (ts.isIdentifier(name)) {
    names.add(name.text)
    return
  }
  for (const element of name.elements) {
    if (!ts.isOmittedExpression(element)) collectBindingNames(element.name, names)
  }
}

function extractUnboundCalls(source: string, targets: ReadonlySet<string>): Array<{ name: string, line: number }> {
  const calls: Array<{ name: string, line: number }> = []
  for (const fragment of scriptFragments(source)) {
    const file = ts.createSourceFile(source, fragment.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const rootScope: LexicalScope = { bindings: new Set() }
    const scopes = new Map<ts.Node, LexicalScope>()
    collectLexicalScopes(file, rootScope, scopes)
    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)
        && targets.has(node.expression.text) && !isBound(node.expression.text, scopes.get(node))) {
        calls.push({
          name: node.expression.text,
          line: file.getLineAndCharacterOfPosition(node.expression.getStart(file)).line + fragment.startLine
        })
      }
      ts.forEachChild(node, visit)
    }
    visit(file)
  }
  return calls
}

type LexicalScope = {
  readonly parent?: LexicalScope
  readonly bindings: Set<string>
}

function collectLexicalScopes(node: ts.Node, incoming: LexicalScope, scopes: Map<ts.Node, LexicalScope>) {
  let scope = incoming
  if (ts.isFunctionDeclaration(node) && node.name) incoming.bindings.add(node.name.text)
  if (ts.isClassDeclaration(node) && node.name) incoming.bindings.add(node.name.text)
  if (ts.isFunctionLike(node)) {
    scope = { parent: incoming, bindings: new Set() }
    if (ts.isFunctionExpression(node) && node.name) scope.bindings.add(node.name.text)
    for (const parameter of node.parameters) collectBindingNames(parameter.name, scope.bindings)
  } else if (node !== node.getSourceFile() && (ts.isBlock(node) || ts.isCatchClause(node))) {
    scope = { parent: incoming, bindings: new Set() }
    if (ts.isCatchClause(node) && node.variableDeclaration) {
      collectBindingNames(node.variableDeclaration.name, scope.bindings)
    }
  }
  scopes.set(node, scope)

  if (ts.isImportDeclaration(node) && node.importClause) {
    if (node.importClause.name) scope.bindings.add(node.importClause.name.text)
    const bindings = node.importClause.namedBindings
    if (bindings && ts.isNamespaceImport(bindings)) scope.bindings.add(bindings.name.text)
    if (bindings && ts.isNamedImports(bindings)) {
      for (const element of bindings.elements) scope.bindings.add(element.name.text)
    }
  }
  if (ts.isVariableDeclaration(node)) collectBindingNames(node.name, scope.bindings)

  ts.forEachChild(node, child => collectLexicalScopes(child, scope, scopes))
}

function isBound(name: string, scope: LexicalScope | undefined): boolean {
  for (let current = scope; current; current = current.parent) {
    if (current.bindings.has(name)) return true
  }
  return false
}

export function activeFrontendViolations(options: ScanOptions): ArchitectureViolation[] {
  const repositoryRoot = resolve(options.repositoryRoot)
  const rulesFile = options.rulesFile ?? resolve(repositoryRoot, 'architecture/module-contract-rules.json')
  const baselineFile = options.baselineFile ?? resolve(repositoryRoot, 'architecture/module-boundary-baseline.json')
  const baseline = loadBaseline(repositoryRoot, rulesFile, baselineFile)
  return scanFrontendArchitecture(options).filter(item => !baseline.has(key(item)))
}

function loadBaseline(repositoryRoot: string, rulesFile: string, baselineFile: string): Set<string> {
  const rules = JSON.parse(readFileSync(rulesFile, 'utf8')) as { version?: number, rules?: Array<{ id?: string }> }
  const baseline = JSON.parse(readFileSync(baselineFile, 'utf8')) as { version?: number, entries?: BaselineEntry[] }
  if (rules.version !== 1 || baseline.version !== 1 || !Array.isArray(rules.rules) || !Array.isArray(baseline.entries)) {
    throw new Error('Architecture rule and baseline files must use schema version 1.')
  }
  const knownRules = new Set(rules.rules.map(rule => rule.id))
  const result = new Set<string>()
  for (const entry of baseline.entries) {
    if (!knownRules.has(entry.rule)) throw new Error(`Unknown baseline rule: ${entry.rule}`)
    if ([entry.rule, entry.source, entry.target].some(value => !value || value.includes('*'))) {
      throw new Error('Baseline rule, source and target must be exact non-wildcard strings.')
    }
    if (!/^#\d+$/.test(entry.tracking_issue) || !entry.reason?.trim()) {
      throw new Error('Every baseline entry needs a reason and a tracking issue like #123.')
    }
    if (!existsSync(resolve(repositoryRoot, entry.source))) {
      throw new Error(`Baseline source does not exist: ${entry.source}`)
    }
    const entryKey = key(entry)
    if (result.has(entryKey)) throw new Error(`Duplicate baseline entry: ${entryKey}`)
    result.add(entryKey)
  }
  return result
}

function resolvesInside(specifier: string, source: string, frontendRoot: string, targetRoot: string): boolean {
  let target: string | undefined
  if (specifier.startsWith('~/') || specifier.startsWith('@/')) {
    target = resolve(frontendRoot, specifier.slice(2))
  } else if (specifier.startsWith('.')) {
    target = resolve(dirname(source), specifier)
  } else if (specifier.includes('frontend-modules/')) {
    target = resolve(frontendRoot, specifier.slice(specifier.indexOf('frontend-modules/')))
  }
  return target !== undefined && isInside(targetRoot, target)
}

function isInside(parent: string, child: string): boolean {
  const path = relative(parent, child)
  return path === '' || (path !== '..' && !path.startsWith(`..${sep}`))
}

function walkSourceFiles(directory: string): string[] {
  if (!existsSync(directory)) return []
  return readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name, 'en'))
    .flatMap(entry => {
      const path = resolve(directory, entry.name)
      return entry.isDirectory() ? walkSourceFiles(path) : sourceExtension.test(path) ? [path] : []
    })
}

function scriptFragments(source: string): Array<{ text: string, startLine: number }> {
  const contents = readFileSync(source, 'utf8')
  if (!source.endsWith('.vue')) return [{ text: contents, startLine: 1 }]
  const fragments: Array<{ text: string, startLine: number }> = []
  for (const match of contents.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
    const text = match[1] ?? ''
    const contentStart = (match.index ?? 0) + match[0].indexOf(text)
    fragments.push({ text, startLine: contents.slice(0, contentStart).split('\n').length })
  }
  return fragments
}

function extractImports(source: string): Array<{ specifier: string, line: number }> {
  const imports: Array<{ specifier: string, line: number }> = []
  for (const fragment of scriptFragments(source)) {
    const file = ts.createSourceFile(source, fragment.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const visit = (node: ts.Node) => {
      let literal: ts.StringLiteralLike | undefined
      if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
        literal = node.moduleSpecifier && ts.isStringLiteralLike(node.moduleSpecifier) ? node.moduleSpecifier : undefined
      } else if (ts.isCallExpression(node) && (
        node.expression.kind === ts.SyntaxKind.ImportKeyword
        || (ts.isIdentifier(node.expression) && node.expression.text === 'require')
      )) {
        const argument = node.arguments[0]
        literal = argument && ts.isStringLiteralLike(argument) ? argument : undefined
      }
      if (literal) {
        const line = file.getLineAndCharacterOfPosition(literal.getStart(file)).line + fragment.startLine
        imports.push({ specifier: literal.text, line })
      }
      ts.forEachChild(node, visit)
    }
    visit(file)
  }
  return imports
}

function extractStringLiterals(source: string): Array<{ value: string, line: number }> {
  const literals: Array<{ value: string, line: number }> = []
  for (const fragment of scriptFragments(source)) {
    const file = ts.createSourceFile(source, fragment.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const visit = (node: ts.Node) => {
      if (ts.isStringLiteralLike(node)) {
        literals.push({
          value: node.text,
          line: file.getLineAndCharacterOfPosition(node.getStart(file)).line + fragment.startLine
        })
      }
      ts.forEachChild(node, visit)
    }
    visit(file)
  }
  return literals
}

function makeViolation(
  repositoryRoot: string,
  rule: ArchitectureViolation['rule'],
  source: string,
  imported: { specifier: string, line: number }
): ArchitectureViolation {
  return { rule, source: relative(repositoryRoot, source).split(sep).join('/'), target: imported.specifier, line: imported.line }
}

function key(item: { rule: string, source: string, target: string }): string {
  return JSON.stringify([item.rule, item.source, item.target])
}

function unique(items: ArchitectureViolation[]): ArchitectureViolation[] {
  return [...new Map(items.map(item => [key(item), item])).values()]
}
