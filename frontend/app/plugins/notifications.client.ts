export default defineNuxtPlugin(() => {
  const auth = useAuthStore()
  const notifications = useNotificationsStore()

  watch(() => auth.authenticated, (authenticated) => {
    if (!authenticated) {
      notifications.reset()
      return
    }
    void notifications.fetchNotifications()
    void notifications.loadSubscriptions()
    notifications.connect()
  }, { immediate: true })

  const refreshOnFocus = () => {
    if (document.visibilityState === 'visible' && auth.authenticated) {
      void notifications.fetchNotifications()
    }
  }
  window.addEventListener('visibilitychange', refreshOnFocus)
})
