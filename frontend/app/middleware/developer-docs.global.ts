import { projectConfig } from '~/config/project'

export default defineNuxtRouteMiddleware((to) => {
  const requestUrl = useRequestURL()
  const developerUrl = new URL(projectConfig.documentation.developerUrl)
  const developerHost = developerUrl.hostname
  const host = requestUrl.hostname
  const developerPrefix = '/dokumentation/entwickler'

  if (host === developerHost) {
    if (to.path.startsWith(developerPrefix)) return
    const suffix = to.path === '/' ? '' : to.path
    return navigateTo(`${developerPrefix}${suffix}`, { redirectCode: 302 })
  }

  if (host === 'stadtplaner.oklabflensburg.de' && to.path.startsWith(developerPrefix)) {
    const suffix = to.path.slice(developerPrefix.length)
    return navigateTo(`${projectConfig.documentation.developerUrl}${suffix || '/'}`, {
      external: true,
      redirectCode: 301
    })
  }
})
