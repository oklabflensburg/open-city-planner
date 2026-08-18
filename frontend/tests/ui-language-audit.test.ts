import { execFileSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'

describe('förmliche Sprache in nutzersichtbaren Ressourcen', () => {
  it('enthält keine unbeabsichtigte Du-Ansprache oder informelle Imperative', () => {
    const output = execFileSync(process.execPath, ['scripts/audit-ui-language.mjs'], { encoding: 'utf8' })
    expect(output).toMatch(/0 unerlaubte Treffer/)
  })
})
