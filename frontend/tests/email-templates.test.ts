import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../app/${path}`, import.meta.url)),
  'utf8'
)

describe('administrierbare E-Mail-Vorlagen', () => {
  it('shows the menu only in the existing superuser navigation', () => {
    const header = appFile('components/layout/AppHeader.vue')
    expect(header).toContain("authStore.user?.is_superuser ?")
    expect(header).toContain("{ label: 'E-Mail-Vorlagen', to: '/admin/email-vorlagen' }")
  })

  it('protects list and editor with the superuser middleware', () => {
    expect(appFile('pages/admin/email-vorlagen/index.vue')).toContain("middleware: 'superuser'")
    expect(appFile('pages/admin/email-vorlagen/[key].vue')).toContain("middleware: 'superuser'")
  })

  it('supports load, save, preview, test send and reset through dedicated APIs', () => {
    const composable = appFile('composables/useEmailTemplates.ts')
    expect(composable).toContain("method: 'PATCH'")
    expect(composable).toContain('/preview`')
    expect(composable).toContain('/test-send`')
    expect(composable).toContain('/reset`')
    expect(composable).toContain('version: template.version')
  })

  it('isolates the server-rendered preview and never injects it with v-html', () => {
    const editor = appFile('pages/admin/email-vorlagen/[key].vue')
    expect(editor).toContain('sandbox=""')
    expect(editor).toContain(':srcdoc="preview.html"')
    expect(editor).not.toContain('v-html')
  })

  it('offers all editor actions and explains immutable legal framing', () => {
    const editor = appFile('pages/admin/email-vorlagen/[key].vue')
    expect(editor).toContain('Änderungen speichern')
    expect(editor).toContain('Vorschau')
    expect(editor).toContain('Test-E-Mail senden')
    expect(editor).toContain('Standard wiederherstellen')
    expect(editor).toContain('Impressum und Datenschutz werden unveränderlich ergänzt')
  })
})
