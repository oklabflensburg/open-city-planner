import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, relative, resolve, sep } from 'node:path'
import ts from 'typescript'

export type ArchitectureViolation = {
  rule: 'ARCH-FE-HOST-001' | 'ARCH-FE-MODULE-001'
  source: string
  target: string
  line: number
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
  rulesFile?: string
  baselineFile?: string
}

const sourceExtension = /\.(?:vue|[cm]?[jt]sx?)$/

export function scanFrontendArchitecture(options: ScanOptions): ArchitectureViolation[] {
  const repositoryRoot = resolve(options.repositoryRoot)
  const frontendRoot = resolve(options.frontendRoot ?? resolve(repositoryRoot, 'frontend'))
  const modulesRoot = resolve(frontendRoot, 'frontend-modules')
  const moduleIds = existsSync(modulesRoot)
    ? readdirSync(modulesRoot, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .map(entry => entry.name)
    : []
  const violations: ArchitectureViolation[] = []

  for (const moduleId of moduleIds) {
    const moduleRoot = resolve(modulesRoot, moduleId)
    for (const source of walkSourceFiles(moduleRoot)) {
      for (const imported of extractImports(source)) {
        if (isForbiddenModuleImport(imported.specifier, source, moduleRoot, modulesRoot)) {
          violations.push(makeViolation(repositoryRoot, 'ARCH-FE-MODULE-001', source, imported))
        }
      }
    }
  }

  const hostSources = [
    ...walkSourceFiles(resolve(frontendRoot, 'module-host')),
    ...walkSourceFiles(resolve(frontendRoot, 'app')),
    resolve(frontendRoot, 'nuxt.config.ts')
  ].filter((source, index, all) => existsSync(source) && all.indexOf(source) === index)
  for (const source of hostSources) {
    for (const imported of extractImports(source)) {
      if (resolvesInside(imported.specifier, source, frontendRoot, modulesRoot)) {
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

function isForbiddenModuleImport(specifier: string, source: string, moduleRoot: string, modulesRoot: string): boolean {
  if (specifier.startsWith('~/') || specifier.startsWith('@/')) return true
  if (specifier.includes('frontend-modules/')) return true
  if (!specifier.startsWith('.')) return false
  const target = resolve(dirname(source), specifier)
  return !isInside(moduleRoot, target) || (isInside(modulesRoot, target) && !isInside(moduleRoot, target))
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
      } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
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
