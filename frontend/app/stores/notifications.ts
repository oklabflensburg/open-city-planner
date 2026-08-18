import { defineStore } from 'pinia'
import type {
  AppNotification,
  AppToast,
  NotificationCategory,
  NotificationPage,
  NotificationPreferences,
  NotificationPriority,
  NotificationSubscription
} from '~/types/notification'
import { buildApiUrl } from '~/utils/apiUrl'
import { shouldToastNotification } from '~/utils/notifications'

const toastTimers = new Map<string, ReturnType<typeof setTimeout>>()

export const useNotificationsStore = defineStore('notifications', {
  state: () => ({
    items: [] as AppNotification[],
    unreadCount: 0,
    total: 0,
    page: 1,
    pages: 1,
    loading: false,
    connectionState: 'disconnected' as 'disconnected' | 'connecting' | 'connected',
    source: null as EventSource | null,
    preferences: null as NotificationPreferences | null,
    preferencesLoading: false,
    subscriptions: [] as NotificationSubscription[],
    subscriptionsLoading: false,
    subscriptionsLoaded: false,
    toasts: [] as AppToast[]
  }),
  actions: {
    async fetchNotifications(options: { page?: number, category?: NotificationCategory, unreadOnly?: boolean, append?: boolean } = {}) {
      if (!useAuthStore().authenticated) return
      this.loading = true
      try {
        const page = options.page || 1
        const query = new URLSearchParams({ page: String(page), page_size: '30' })
        if (options.category) query.set('category', options.category)
        if (options.unreadOnly) query.set('unread_only', 'true')
        const result = await useApi().request<NotificationPage>(`/notifications?${query}`)
        this.items = options.append ? mergeNotifications(this.items, result.items) : mergeNotifications([], result.items)
        this.unreadCount = result.unread_count
        this.total = result.total
        this.page = result.page
        this.pages = result.pages
      } finally {
        this.loading = false
      }
    },
    async refreshUnreadCount() {
      if (!useAuthStore().authenticated) return
      const result = await useApi().request<{ unread_count: number }>('/notifications/unread-count')
      this.unreadCount = result.unread_count
    },
    connect() {
      if (!import.meta.client || !useAuthStore().authenticated || this.source) return
      const config = useRuntimeConfig()
      this.connectionState = 'connecting'
      const source = new EventSource(buildApiUrl(config.public.apiBaseUrl, '/notifications/stream'), { withCredentials: true })
      this.source = source
      source.addEventListener('ready', () => {
        const reconnected = this.connectionState !== 'connecting'
        this.connectionState = 'connected'
        if (reconnected) void this.fetchNotifications()
      })
      source.addEventListener('notification.created', (event) => {
        try {
          this.handleRealtimeNotification(JSON.parse((event as MessageEvent).data) as AppNotification)
        } catch (error) {
          if (import.meta.dev) console.warn('Invalid notification event', error)
        }
      })
      source.onerror = () => { this.connectionState = 'disconnected' }
    },
    disconnect() {
      this.source?.close()
      this.source = null
      this.connectionState = 'disconnected'
    },
    handleRealtimeNotification(item: AppNotification) {
      const previous = this.items.find(value => value.id === item.id)
      this.items = mergeNotifications(this.items, [item])
      if (!previous || previous.is_read) this.unreadCount += 1
      if (shouldToastNotification(item.priority)) {
        this.showToast({ title: item.title, message: item.message, priority: item.priority })
      }
    },
    async markRead(id: string) {
      const item = this.items.find(value => value.id === id)
      if (!item || item.is_read) return
      item.is_read = true
      item.read_at = new Date().toISOString()
      this.unreadCount = Math.max(0, this.unreadCount - 1)
      try {
        await useApi().request(`/notifications/${id}/read`, { method: 'PATCH' })
      } catch (error) {
        item.is_read = false
        item.read_at = null
        this.unreadCount += 1
        throw error
      }
    },
    async markAllRead() {
      const unread = this.items.filter(item => !item.is_read)
      unread.forEach((item) => { item.is_read = true; item.read_at = new Date().toISOString() })
      const previousCount = this.unreadCount
      this.unreadCount = 0
      try {
        await useApi().request('/notifications/read-all', { method: 'POST' })
      } catch (error) {
        unread.forEach((item) => { item.is_read = false; item.read_at = null })
        this.unreadCount = previousCount
        throw error
      }
    },
    async loadPreferences() {
      this.preferencesLoading = true
      try {
        this.preferences = await useApi().request<NotificationPreferences>('/notifications/preferences')
      } finally {
        this.preferencesLoading = false
      }
    },
    async savePreferences(payload: Partial<NotificationPreferences>) {
      this.preferences = await useApi().request<NotificationPreferences>('/notifications/preferences', {
        method: 'PATCH', body: JSON.stringify(payload)
      })
      return this.preferences
    },
    async loadSubscriptions() {
      this.subscriptionsLoading = true
      try {
        this.subscriptions = await useApi().request<NotificationSubscription[]>('/notifications/subscriptions')
      } finally {
        this.subscriptionsLoading = false
        this.subscriptionsLoaded = true
      }
    },
    isFollowing(resourceType: 'POLYGON' | 'AREA', resourceId: string) {
      return this.subscriptions.some(item => item.resource_type === resourceType && item.resource_id === resourceId)
    },
    async follow(resourceType: 'POLYGON' | 'AREA', resourceId: string) {
      const item = await useApi().request<NotificationSubscription>('/notifications/subscriptions', {
        method: 'PUT', body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId, event_types: [] })
      })
      this.subscriptions = [...this.subscriptions.filter(value => !(value.resource_type === resourceType && value.resource_id === resourceId)), item]
    },
    async unfollow(resourceType: 'POLYGON' | 'AREA', resourceId: string) {
      await useApi().request(`/notifications/subscriptions/${resourceType}/${encodeURIComponent(resourceId)}`, { method: 'DELETE' })
      this.subscriptions = this.subscriptions.filter(value => !(value.resource_type === resourceType && value.resource_id === resourceId))
    },
    showToast(input: { title: string, message?: string, priority?: NotificationPriority }) {
      const id = crypto.randomUUID()
      this.toasts = [...this.toasts.slice(-2), { id, title: input.title, message: input.message, priority: input.priority || 'SUCCESS' }]
      toastTimers.set(id, setTimeout(() => this.dismissToast(id), 5000))
    },
    dismissToast(id: string) {
      this.toasts = this.toasts.filter(item => item.id !== id)
      clearTimeout(toastTimers.get(id))
      toastTimers.delete(id)
    },
    reset() {
      this.disconnect()
      this.items = []
      this.unreadCount = 0
      this.total = 0
      this.preferences = null
      this.subscriptions = []
      this.subscriptionsLoading = false
      this.subscriptionsLoaded = false
    }
  }
})

export function mergeNotifications(current: AppNotification[], incoming: AppNotification[]) {
  const byId = new Map(current.map(item => [item.id, item]))
  incoming.forEach(item => byId.set(item.id, item))
  return [...byId.values()].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
}
