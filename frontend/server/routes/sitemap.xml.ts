import type { PolygonSitemapEntry } from '~/types/geo'
import type { PublicAreaSitemapEntry } from '~/types/publicAreaReference'
import { buildAbsoluteUrl } from '~/utils/seo'
import { documentationPaths } from '~/config/documentation'
import { buildSitemapXml, type SitemapUrl } from '../utils/sitemap'

const STATIC_PATHS = ['/', '/karte', '/gebiete', '/vergleich', '/ueber-das-projekt', '/open-data', '/kontakt', ...documentationPaths]

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const apiBaseUrl = config.apiInternalBaseUrl || config.public.apiBaseUrl
  const [entries, areas] = await Promise.all([
    $fetch<PolygonSitemapEntry[]>(`${apiBaseUrl}/polygons/sitemap`, {
      headers: { 'X-Request-ID': event.context.requestId }
    }),
    $fetch<PublicAreaSitemapEntry[]>(`${apiBaseUrl}/analysis-areas/sitemap`, {
      headers: { 'X-Request-ID': event.context.requestId }
    })
  ])
  const urls: SitemapUrl[] = [
    ...STATIC_PATHS.map(path => ({ loc: buildAbsoluteUrl(config.public.siteUrl, path) })),
    ...entries.map(entry => ({
      loc: buildAbsoluteUrl(config.public.siteUrl, `/flaechen/${entry.slug}`),
      lastmod: entry.updated_at
    })),
    ...areas.map(area => ({
      loc: buildAbsoluteUrl(config.public.siteUrl, `/gebiete/${area.slug}`),
      lastmod: area.updated_at
    }))
  ]

  setResponseHeader(event, 'content-type', 'application/xml; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'no-cache, must-revalidate')
  return buildSitemapXml(urls)
})
