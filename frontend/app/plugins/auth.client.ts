import { sanitizeInternalRedirect } from '~/utils/redirect'

export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()
  const route = useRoute()

  watch(() => authStore.sessionExpired, async (expired) => {
    if (!expired || route.path === '/login') return
    const redirect = sanitizeInternalRedirect(route.fullPath)
    authStore.sessionExpired = false
    await navigateTo(
      `/login?redirect=${encodeURIComponent(redirect)}&session_expired=1`,
      { replace: true }
    )
  })

  await authStore.initialize()
})
