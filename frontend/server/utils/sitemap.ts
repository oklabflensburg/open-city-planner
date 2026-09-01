export type SitemapUrl = { loc: string; lastmod?: string }
export type SitemapPath = { path: string; lastmod?: string }

export interface ResolvedModuleSitemap {
  staticRoutes: string[]
  dynamicRoutes: Array<{
    route: string
    entries: Array<{ slug: string, updated_at?: string }>
  }>
}

export function moduleSitemapPaths(modules: ResolvedModuleSitemap[]): SitemapPath[] {
  return modules.flatMap(module => [
    ...module.staticRoutes.map(path => ({ path })),
    ...module.dynamicRoutes.flatMap(provider => provider.entries.map(entry => ({
      path: provider.route.replace(':slug', encodeURIComponent(entry.slug)),
      lastmod: entry.updated_at
    })))
  ])
}

export function buildSitemapXml(urls: SitemapUrl[]) {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(url => `  <url>\n    <loc>${escapeXml(url.loc)}</loc>${url.lastmod ? `\n    <lastmod>${escapeXml(url.lastmod)}</lastmod>` : ''}\n  </url>`).join('\n')}\n</urlset>\n`
}

export function escapeXml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}
