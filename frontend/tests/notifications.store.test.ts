import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useNotificationsStore, mergeNotifications } from '~/stores/notifications'
import type { AppNotification } from '~/types/notification'
import { formatNotificationTime, safeNotificationTarget, shouldToastNotification } from '~/utils/notifications'

function notification(id: string, overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id, event_type: 'GIS_AREA_UPDATED', category: 'GIS', priority: 'INFO',
    title: 'Fläche aktualisiert', message: 'Testfläche wurde geändert.',
    resource_type: 'POLYGON', resource_id: 'polygon-1', resource_slug: 'testflaeche',
    action_url: '/flaechen/testflaeche', action_label: 'Fläche ansehen',
    is_read: false, read_at: null, created_at: '2026-08-17T10:00:00Z', metadata: {},
    ...overrides
  }
}

describe('notifications store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('useAuthStore', () => ({ authenticated: true }))
  })

  it('deduplicates fetch and realtime payloads by id and keeps newest first', () => {
    const merged = mergeNotifications(
      [notification('one')],
      [notification('one', { message: 'Neu', created_at: '2026-08-17T11:00:00Z' }), notification('two', { created_at: '2026-08-17T10:30:00Z' })]
    )
    expect(merged.map(item => item.id)).toEqual(['one', 'two'])
    expect(merged[0].message).toBe('Neu')
  })

  it('merges realtime notifications once and only toasts relevant priorities', () => {
    const store = useNotificationsStore()
    const toast = vi.spyOn(store, 'showToast')
    store.handleRealtimeNotification(notification('one'))
    store.handleRealtimeNotification(notification('one'))
    store.handleRealtimeNotification(notification('two', { priority: 'ERROR' }))
    expect(store.items).toHaveLength(2)
    expect(store.unreadCount).toBe(2)
    expect(toast).toHaveBeenCalledTimes(1)
    expect(shouldToastNotification('INFO')).toBe(false)
    expect(shouldToastNotification('ACTION_REQUIRED')).toBe(true)
  })

  it('optimistically marks one or all notifications read', async () => {
    const request = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('useApi', () => ({ request }))
    const store = useNotificationsStore()
    store.items = [notification('one'), notification('two')]
    store.unreadCount = 2
    await store.markRead('one')
    expect(store.unreadCount).toBe(1)
    expect(store.items[0].is_read).toBe(true)
    await store.markAllRead()
    expect(store.unreadCount).toBe(0)
    expect(store.items.every(item => item.is_read)).toBe(true)
  })

  it('formats relative times and rejects external action URLs', () => {
    expect(formatNotificationTime('2026-08-17T09:55:00Z', new Date('2026-08-17T10:00:00Z'))).toBe('vor 5 Min.')
    expect(safeNotificationTarget('/verwaltung')).toBe('/verwaltung')
    expect(safeNotificationTarget('https://evil.example')).toBeNull()
    expect(safeNotificationTarget('//evil.example')).toBeNull()
  })
})
