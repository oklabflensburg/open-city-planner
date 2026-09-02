import type { PolygonSitemapEntry } from '~/types/geo'
import { buildAbsoluteUrl } from '~/utils/seo'
import { documentationPaths } from '~/config/documentation'
import { buildSitemapXml, moduleSitemapPaths, type SitemapUrl } from '../utils/sitemap'

const STATIC_PATHS = ['/', '/karte', '/ueber-das-projekt', '/open-data', '/kontakt', ...documentationPaths]

interface ModuleSitemapEntry {
  slug: string
  updated_at?: string
}

interface ModuleSitemapContribution {
  moduleId: string
  staticRoutes: string[]
  dynamicRoutes: Array<{ route: string, endpoint: string }>
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const apiBaseUrl = config.apiInternalBaseUrl || config.public.apiBaseUrl
  const moduleContributions = (
    config.public.frontendSitemapContributions ?? []
  ) as ModuleSitemapContribution[]
  const [entries, dynamicEntries] = await Promise.all([
    $fetch<PolygonSitemapEntry[]>(`${apiBaseUrl}/polygons/sitemap`, {
      headers: { 'X-Request-ID': event.context.requestId }
    }),
    Promise.all(moduleContributions.flatMap(contribution => contribution.dynamicRoutes.map(async route => ({
      moduleId: contribution.moduleId,
      route: route.route,
      entries: await $fetch<ModuleSitemapEntry[]>(`${apiBaseUrl}${route.endpoint}`, {
        headers: { 'X-Request-ID': event.context.requestId }
      })
    }))))
  ])
  const urls: SitemapUrl[] = [
    ...STATIC_PATHS.map(path => ({ loc: buildAbsoluteUrl(config.public.siteUrl, path) })),
    ...entries.map(entry => ({
      loc: buildAbsoluteUrl(config.public.siteUrl, `/flaechen/${entry.slug}`),
      lastmod: entry.updated_at
    })),
    ...moduleSitemapPaths(moduleContributions.map(contribution => ({
      staticRoutes: contribution.staticRoutes,
      dynamicRoutes: contribution.dynamicRoutes.map(route => ({
        route: route.route,
        entries: dynamicEntries.find(provider => (
          provider.moduleId === contribution.moduleId && provider.route === route.route
        ))?.entries ?? []
      }))
    }))).map(entry => ({
      loc: buildAbsoluteUrl(config.public.siteUrl, entry.path),
      lastmod: entry.lastmod
    }))
  ]

  setResponseHeader(event, 'content-type', 'application/xml; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'no-cache, must-revalidate')
  return buildSitemapXml(urls)
})
