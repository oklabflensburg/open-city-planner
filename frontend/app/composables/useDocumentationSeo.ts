import type { DocumentationPage } from '~/types/documentation'
import { documentationPath } from '~/utils/documentation'
import { buildBreadcrumbStructuredData, buildWebPageStructuredData } from '~/utils/seo'

export function useDocumentationSeo(page: DocumentationPage) {
  const config = useRuntimeConfig()
  const path = documentationPath(page)
  const breadcrumbs = [
    { name: 'Startseite', path: '/' },
    { name: 'Dokumentation', path: '/dokumentation' },
    ...(page.slug ? [{ name: page.title, path }] : [])
  ]

  usePageSeo({
    title: page.title,
    description: page.description,
    path,
    type: 'article',
    robots: 'index,follow',
    structuredData: [
      buildBreadcrumbStructuredData(config.public.siteUrl, breadcrumbs),
      buildWebPageStructuredData(config.public.siteUrl, path, page.title, page.description)
    ]
  })
}
