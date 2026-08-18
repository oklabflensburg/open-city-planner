import { readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))
const repositoryRoot = resolve(frontendRoot, '..')
const roots = ['frontend/app', 'frontend/public', 'backend/app', 'docs']
const extensions = new Set(['.vue', '.ts', '.js', '.mjs', '.py', '.html', '.txt', '.md'])
const excludedDirectories = new Set(['.nuxt', '.output', '.venv', 'node_modules', '__pycache__'])
const forbidden = [
  { label: 'informelle Anrede', expression: /\b(?:du|dein(?:e|em|en|er|es)?|dir|dich)\b/giu },
  { label: 'informeller Imperativ', expression: /\bBitte\s+(?:melde|bestätige|hinterlege|lade|wähle|gib|prüfe|öffne|klicke|versuche|kontaktiere|registriere|erstelle|lege|fordere|verwalte|verbinde|füge|lösche|bearbeite|zeige|zeichne|speichere|wende)\b/giu },
  { label: 'informeller Imperativ', expression: /(?:['"`>]|^)\s*(?:Melde|Bestätige|Hinterlege|Lade|Wähle|Gib|Prüfe|Öffne|Klicke|Kontaktiere|Registriere|Erstelle|Lege|Fordere|Verwalte|Verbinde|Füge|Lösche|Bearbeite|Zeige|Zeichne|Speichere|Wende|Übertrage)\b/gu },
  { label: 'informelle Aufforderung', expression: /\b(?:Passe\s+Suche|Ändere\s+den|Suche\s+frei|grenze\s+die|setze\s+die\s+Filter)\b/giu }
]

function files(directory) {
  if (!statSync(directory).isDirectory()) return [directory]
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    if (entry.isDirectory() && excludedDirectories.has(entry.name)) return []
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return files(path)
    return extensions.has(extname(entry.name)) ? [path] : []
  })
}

function visibleLines(path) {
  const markdown = extname(path) === '.md'
  let inFence = false
  return readFileSync(path, 'utf8').split(/\r?\n/).map((text, index) => {
    if (markdown && /^\s*```/.test(text)) {
      inFence = !inFence
      return null
    }
    return inFence ? null : { number: index + 1, text: markdown ? text.replace(/`[^`]*`/g, '') : text }
  }).filter(Boolean)
}

export function auditUiLanguage() {
  const checked = roots.flatMap(root => files(resolve(repositoryRoot, root)))
  const findings = []
  for (const path of checked) {
    for (const line of visibleLines(path)) {
      for (const rule of forbidden) {
        rule.expression.lastIndex = 0
        const match = rule.expression.exec(line.text)
        if (match) findings.push({ file: relative(repositoryRoot, path), line: line.number, match: match[0], rule: rule.label })
      }
    }
  }
  return { checked: checked.length, findings }
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedDirectly) {
  const result = auditUiLanguage()
  for (const finding of result.findings) {
    process.stderr.write(`${finding.file}:${finding.line}: ${finding.rule}: „${finding.match}“\n`)
  }
  process.stdout.write(`${result.checked} nutzersichtbare Ressourcen geprüft, ${result.findings.length} unerlaubte Treffer.\n`)
  if (result.findings.length) process.exitCode = 1
}
