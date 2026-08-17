import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appRoot = fileURLToPath(new URL('../app', import.meta.url))
const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

function productiveFiles(directory = appRoot): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = `${directory}/${entry}`
    return statSync(path).isDirectory() ? productiveFiles(path) : /\.(?:vue|ts|js)$/.test(path) ? [path] : []
  })
}

describe('central modal architecture', () => {
  it('provides one accessible and responsive modal shell', () => {
    const modal = appFile('components/ui/AppModal.vue')
    expect(modal).toContain('<Teleport to="body">')
    expect(modal).toContain('aria-modal="true"')
    expect(modal).toContain(':aria-labelledby="titleId"')
    expect(modal).toContain(':aria-describedby="modalDescribedBy"')
    expect(modal).toContain("type ModalSize = 'sm' | 'md' | 'lg' | 'xl'")
    expect(modal).toContain('max-h-[calc(100dvh-2rem)]')
    expect(modal).toContain('overflow-y-auto overscroll-contain')
    expect(modal).toContain('env(safe-area-inset-top)')
    expect(modal).toContain('env(safe-area-inset-bottom)')
  })

  it('closes consistently and blocks closing while busy', () => {
    const modal = appFile('components/ui/AppModal.vue')
    expect(modal).toContain('@click.self="requestOverlayClose"')
    expect(modal).toContain("event.key === 'Escape'")
    expect(modal).toContain('if (props.busy) return')
    expect(modal).toContain("emit('update:open', false)")
    expect(modal).toContain('closeOnOverlay')
    expect(modal).toContain('closeOnEscape')
  })

  it('traps and returns focus and uses a nested-safe body lock', () => {
    const modal = appFile('components/ui/AppModal.vue')
    expect(modal).toContain("event.key !== 'Tab'")
    expect(modal).toContain('[data-autofocus]:not([disabled])')
    expect(modal).toContain('returnFocusTo?.focus()')
    expect(modal).toContain('modalLockCount += 1')
    expect(modal).toContain("document.body.classList.add('modal-open')")
    expect(appFile('assets/css/main.css')).toContain('body.modal-open')
  })

  it('supports default, warning and danger confirmations with loading and errors', () => {
    const confirmation = appFile('components/ui/AppConfirmDialog.vue')
    expect(confirmation).toContain("type ConfirmVariant = 'default' | 'warning' | 'danger'")
    expect(confirmation).toContain('data-autofocus')
    expect(confirmation).toContain(':disabled="loading"')
    expect(confirmation).toContain('role="alertdialog"')
    expect(confirmation).toContain('role="alert"')
    expect(confirmation).toContain("emit('cancel')")
    expect(confirmation).toContain("$emit('confirm')")
  })

  it('uses the confirmation shell for every critical application action', () => {
    expect(appFile('components/polygon/PolygonDeleteSection.vue')).toContain('<AppConfirmDialog')
    expect(appFile('components/admin/AdminUserDialog.vue')).toContain('<AppConfirmDialog')
    expect(appFile('components/auth/OAuthAccountList.vue')).toContain('<AppConfirmDialog')
    expect(appFile('components/user/AvatarUploader.vue')).toContain('<AppConfirmDialog')
    expect(appFile('pages/profil/sicherheit.vue')).toContain('<AppConfirmDialog')
    expect(appFile('components/profile/AccountDangerZone.vue')).toContain('<AppConfirmDialog')
  })

  it('contains no native browser dialogs in productive frontend code', () => {
    const nativeDialog = /\b(?:window\.)?(?:alert|confirm|prompt)\s*\(/
    const offenders = productiveFiles().filter(path => nativeDialog.test(readFileSync(path, 'utf8')))
    expect(offenders).toEqual([])
  })
})
