import type { PolygonSitemapEntry } from '~/types/geo'
import { buildAbsoluteUrl } from '~/utils/seo'
import { buildSitemapXml, type SitemapUrl } from '../utils/sitemap'

const STATIC_PATHS = ['/', '/ueber-das-projekt', '/open-data', '/kontakt']

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const entries = await $fetch<PolygonSitemapEntry[]>(`${config.public.apiBaseUrl}/polygons/sitemap`)
  const urls: SitemapUrl[] = [
    ...STATIC_PATHS.map(path => ({ loc: buildAbsoluteUrl(config.public.siteUrl, path) })),
    ...entries.map(entry => ({
      loc: buildAbsoluteUrl(config.public.siteUrl, `/flaechen/${entry.slug}`),
      lastmod: entry.updated_at
    }))
  ]

  setResponseHeader(event, 'content-type', 'application/xml; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'public, max-age=300, s-maxage=300')
  return buildSitemapXml(urls)
})
