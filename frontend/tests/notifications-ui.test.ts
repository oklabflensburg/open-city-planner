import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('notification center UI', () => {
  it('places an accessible unread bell in desktop and mobile headers', () => {
    const header = appFile('components/layout/AppHeader.vue')
    const bell = appFile('components/notifications/NotificationBell.vue')
    expect(header).toContain('<NotificationBell mode="desktop"')
    expect(header).toContain('<NotificationBell v-if="authStore.authenticated" mode="mobile"')
    expect(bell).toContain('aria-label="Benachrichtigungen"')
    expect(bell).toContain("store.unreadCount > 99 ? '99+'")
    expect(bell).toContain('<AppBottomSheet')
  })

  it('uses semantic unread state, one mobile scroller and safe navigation', () => {
    const center = appFile('components/notifications/NotificationCenterContent.vue')
    const bell = appFile('components/notifications/NotificationBell.vue')
    expect(center).toContain('aria-label="Benachrichtigungsliste"')
    expect(center).toContain('class="sr-only">Ungelesen')
    expect(center).toContain('safeNotificationTarget')
    expect(bell).toContain('content-key="notifications"')
    expect(bell).not.toContain('alert(')
  })

  it('provides autosaved preferences and resource follow controls', () => {
    const preferences = appFile('components/notifications/NotificationPreferencesCard.vue')
    expect(preferences).toContain('createSerialSaveQueue')
    expect(preferences).toContain('Konto- und Sicherheitsmeldungen')
    expect(appFile('pages/profil/index.vue')).toContain('<NotificationPreferencesCard')
    expect(appFile('pages/flaechen/[slug].vue')).toContain('resource-type="POLYGON"')
    expect(appFile('pages/gebiete/[slug].vue')).toContain('resource-type="AREA"')
  })
})
