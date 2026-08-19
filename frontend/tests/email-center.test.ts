import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../app/${path}`, import.meta.url)),
  'utf8'
)

describe('E-Mail-Zentrale', () => {
  it('bündelt Vorlagen, Rundmails und Versand', () => {
    const tabs = appFile('components/admin/EmailCenterTabs.vue')
    expect(tabs).toContain('Vorlagen')
    expect(tabs).toContain('Rundmails')
    expect(tabs).toContain('Versand')
    expect(appFile('components/layout/AppHeader.vue')).toContain('E-Mail-Zentrale')
  })

  it('trennt Entwurf, Vorschau, Test und bestätigten Start', () => {
    const editor = appFile('pages/admin/email-zentrale/rundmails/[id].vue')
    expect(editor).toContain('Entwurf speichern')
    expect(editor).toContain('Testmail an mich')
    expect(editor).toContain('Versand vorbereiten')
    expect(editor).toContain('legalConfirmed')
    expect(editor).toContain('sandbox=""')
  })

  it('zeigt getrennte In-App-, E-Mail- und Newsletter-Schalter', () => {
    const preferences = appFile('components/notifications/NotificationPreferencesCard.vue')
    expect(preferences).toContain('email_enabled')
    expect(preferences).toContain('email_notify_gis')
    expect(preferences).toContain('newsletter_enabled')
    expect(preferences).toContain('Konto- und Sicherheitsmeldungen')
  })

  it('stellt einen öffentlichen Abmeldefluss bereit', () => {
    const page = appFile('pages/email-abmelden.vue')
    expect(page).toContain('/email/unsubscribe?token=')
    expect(page).not.toContain('user.email')
  })
})
