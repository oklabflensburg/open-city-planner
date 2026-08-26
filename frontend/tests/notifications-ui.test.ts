import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')
const moduleFile = (path: string) => readFileSync(fileURLToPath(new URL(`../frontend-modules/analysis-areas/layer/app/${path}`, import.meta.url)), 'utf8')

describe('notification center UI', () => {
  it('places an accessible unread bell in desktop and mobile headers', () => {
    const header = appFile('components/layout/AppHeader.vue')
    const bell = appFile('components/notifications/NotificationBell.vue')
    expect(header).toContain('<LazyNotificationBell data-header-notifications mode="desktop"')
    expect(header).toContain('<LazyNotificationBell v-if="authStore.authenticated" mode="mobile"')
    expect(header.match(/<ClientOnly>/g)).toHaveLength(2)
    expect(header).toContain('<template #fallback>')
    expect(header).toContain('class="size-11 shrink-0"')
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
    expect(moduleFile('pages/gebiete/[slug].vue')).toContain('resource-type="AREA"')
  })

  it('keeps polygon follow as a stable secondary action after title and address on mobile', () => {
    const detail = appFile('pages/flaechen/[slug].vue')
    const follow = appFile('components/notifications/NotificationFollowButton.vue')
    const categoryIndex = detail.indexOf('data-polygon-category')
    const titleIndex = detail.indexOf('data-polygon-title')
    const addressIndex = detail.indexOf('data-polygon-address')
    const actionIndex = detail.indexOf('data-polygon-follow-action')
    const metricsIndex = detail.indexOf('data-polygon-metrics')

    expect(categoryIndex).toBeLessThan(titleIndex)
    expect(titleIndex).toBeLessThan(addressIndex)
    expect(addressIndex).toBeLessThan(actionIndex)
    expect(actionIndex).toBeLessThan(metricsIndex)
    expect(detail).toContain('sm:grid-cols-[minmax(0,1fr)_auto]')
    expect(detail).toContain('<ClientOnly>')
    expect(detail).toContain('min-h-11 w-full animate-pulse')
    expect(detail).not.toContain('class="ml-2 align-middle"')
    expect(follow).toContain('<Button')
    expect(follow).toContain('type="button"')
    expect(follow).toContain(':aria-pressed="following"')
    expect(follow).toContain('invisible col-start-1 row-start-1')
    expect(follow).not.toContain('alert(')
  })
})
