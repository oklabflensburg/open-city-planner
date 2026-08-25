import { buildAbsoluteUrl, buildSeoImageUrl, serializeStructuredData } from '~/utils/seo'

type StructuredData = Record<string, unknown> | Record<string, unknown>[]

export interface PageSeoOptions {
  title: string
  description: string
  path?: string
  siteUrl?: string
  image?: string | null
  imageAlt?: string | null
  imageWidth?: number
  imageHeight?: number
  type?: 'website' | 'article'
  robots?: string
  openGraph?: boolean
  twitter?: boolean
  structuredData?: StructuredData | false
}

export function usePageSeo(options: PageSeoOptions) {
  const config = useRuntimeConfig()
  const siteName = config.public.siteName
  const siteUrl = options.siteUrl || config.public.siteUrl
  const title = options.title === siteName ? siteName : `${options.title} – ${siteName}`
  const canonical = buildAbsoluteUrl(siteUrl, options.path || '/')
  const image = options.image === null
    ? null
    : buildSeoImageUrl(siteUrl, options.image || config.public.defaultOgImage)
  const imageAlt = options.imageAlt || (options.image ? options.title : 'Stadtplaner des OK Lab Flensburg')
  const imageWidth = options.imageWidth ?? 1200
  const imageHeight = options.imageHeight ?? 630
  const openGraph = options.openGraph !== false
  const twitter = options.twitter !== false && openGraph
  const structuredData = options.structuredData === false ? undefined : options.structuredData

  useSeoMeta({
    title,
    description: options.description,
    robots: options.robots || 'index,follow',
    ...(openGraph
      ? {
          ogTitle: title,
          ogDescription: options.description,
          ogType: options.type || 'website',
          ogUrl: canonical,
          ogSiteName: siteName,
          ogLocale: config.public.siteLocale,
          ...(image
            ? {
                ogImage: image,
                ogImageAlt: imageAlt,
                ogImageWidth: imageWidth,
                ogImageHeight: imageHeight
              }
            : {})
        }
      : {}),
    ...(twitter
      ? {
          twitterCard: image ? 'summary_large_image' : 'summary',
          twitterTitle: title,
          twitterDescription: options.description,
          ...(image ? { twitterImage: image, twitterImageAlt: imageAlt } : {})
        }
      : {})
  })

  useHead({
    link: [{ rel: 'canonical', href: canonical }],
    script: structuredData
      ? [{ type: 'application/ld+json', innerHTML: serializeStructuredData(structuredData) }]
      : []
  })
}
