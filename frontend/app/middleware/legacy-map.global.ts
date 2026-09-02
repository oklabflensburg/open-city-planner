export default defineNuxtRouteMiddleware((to) => {
  if (to.path !== '/') return
  const gisKeys = ['polygon', 'flaeche', 'poi']
  if (!gisKeys.some(key => key in to.query)) return
  const query = { ...to.query }
  if (typeof query.area === 'string' && !query.gebiet) query.gebiet = query.area
  delete query.area
  return navigateTo({ path: '/karte', query }, { redirectCode: 301 })
})
