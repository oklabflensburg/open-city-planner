import { sanitizeInternalRedirect } from '~/utils/redirect'

export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()
  if (!authStore.initialized) await authStore.initialize()
  if (!authStore.authenticated) {
    const redirect = sanitizeInternalRedirect(to.fullPath)
    return navigateTo(`/login?redirect=${encodeURIComponent(redirect)}`, { replace: true })
  }
  if (!authStore.user?.is_superuser) {
    return navigateTo('/', { replace: true })
  }
})
