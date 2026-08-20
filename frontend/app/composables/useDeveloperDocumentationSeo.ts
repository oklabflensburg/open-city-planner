import type { DocumentationPage } from '~/types/documentation'
import { projectConfig } from '~/config/project'
import { buildBreadcrumbStructuredData, buildWebPageStructuredData } from '~/utils/seo'

export function useDeveloperDocumentationSeo(page: DocumentationPage) {
  const path = page.slug ? `/${page.slug}` : '/'
  const breadcrumbs = [
    { name: 'Entwicklerdokumentation', path: '/' },
    ...(page.slug ? [{ name: page.title, path }] : [])
  ]

  usePageSeo({
    title: `${page.title} · Entwicklerdokumentation`,
    description: page.description,
    path,
    type: 'article',
    robots: 'index,follow',
    siteUrl: projectConfig.documentation.developerUrl,
    structuredData: [
      buildBreadcrumbStructuredData(projectConfig.documentation.developerUrl, breadcrumbs),
      buildWebPageStructuredData(projectConfig.documentation.developerUrl, path, page.title, page.description)
    ]
  })
}
