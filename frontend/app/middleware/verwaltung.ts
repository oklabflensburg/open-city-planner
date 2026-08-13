import { hasVerwaltungRole } from '~/utils/roles'
import { sanitizeInternalRedirect } from '~/utils/redirect'

export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()
  if (!authStore.initialized) {
    await authStore.initialize()
  }
  if (!authStore.authenticated) {
    const redirect = sanitizeInternalRedirect(to.fullPath)
    return navigateTo(`/login?redirect=${encodeURIComponent(redirect)}`, { replace: true })
  }
  if (!hasVerwaltungRole(authStore.user)) {
    return navigateTo('/', { replace: true })
  }
})
