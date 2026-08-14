import { sanitizeInternalRedirect } from '~/utils/redirect'

export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
  const authStore = useAuthStore()
  if (!authStore.initialized) {
    await authStore.initialize()
  }
  if (!authStore.authenticated) {
    return
  }

  return navigateTo(sanitizeInternalRedirect(to.query.redirect, '/profil'), { replace: true })
})
