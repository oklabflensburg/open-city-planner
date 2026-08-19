import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(
  fileURLToPath(new URL(`../app/${path}`, import.meta.url)),
  'utf8'
)

describe('profile account danger zone', () => {
  const profile = appFile('pages/profil/index.vue')
  const dangerZone = appFile('components/profile/AccountDangerZone.vue')

  it('renders session-dependent profile content only after client hydration', () => {
    expect(profile).toContain('<ClientOnly>')
    expect(profile).toContain('<template #fallback>')
    expect(profile).toContain('Profil wird geladen …')
    expect(profile).toContain('watch(() => authStore.user')
  })

  it('keeps deactivation and permanent deletion visibly separate at the end of profile', () => {
    expect(profile).toContain('<AccountDangerZone />')
    expect(dangerZone).toContain('Gefahrenbereich')
    expect(dangerZone).toContain('Konto deaktivieren')
    expect(dangerZone).toContain('Konto dauerhaft löschen')
    expect(dangerZone).toContain('Eine Reaktivierung ist über die Administration möglich.')
    expect(dangerZone).toContain('variant="danger"')
  })

  it('uses the shared dialogs and a two-stage accessible deletion confirmation', () => {
    expect(dangerZone.match(/<AppConfirmDialog/g)).toHaveLength(2)
    expect(dangerZone).toContain('<AppModal')
    expect(dangerZone).toContain('role="alertdialog"')
    expect(dangerZone).toContain('data-autofocus')
    expect(dangerZone).toContain('LÖSCHEN')
    expect(dangerZone).toContain(':disabled="!deleteConfirmationValid || deleteLoading"')
    expect(dangerZone).toContain('Konto endgültig löschen')
  })

  it('keeps errors in the open dialog and prevents repeated requests', () => {
    expect(dangerZone).toContain('if (deactivateLoading.value) return')
    expect(dangerZone).toContain('if (!deleteConfirmationValid.value || deleteLoading.value) return')
    expect(dangerZone).toContain("deleteError.value = accountErrorMessage")
    expect(dangerZone).toContain('LAST_SUPERUSER_REQUIRED')
    expect(dangerZone).toContain('role="alert"')
  })
})
