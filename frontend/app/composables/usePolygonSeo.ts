import type { PublicPolygonDetail } from '~/types/geo'
import { buildApiUrl } from '~/utils/apiUrl'
import { buildAbsoluteUrl, buildBreadcrumbStructuredData, serializeStructuredData, toMetaDescription } from '~/utils/seo'

export function usePolygonSeo(polygon: MaybeRefOrGetter<PublicPolygonDetail>) {
  const config = useRuntimeConfig()
  const data = computed(() => toValue(polygon))
  const path = computed(() => `/flaechen/${data.value.slug}`)
  const url = computed(() => buildAbsoluteUrl(config.public.siteUrl, path.value))
  const description = computed(() => toMetaDescription(
    data.value.description || '',
    `Informationen zur Fläche „${data.value.name}“ mit Kategorie, Größe und interaktiver Kartendarstellung.`
  ))
  const title = computed(() => `${data.value.name} – ${config.public.siteName}`)
  const image = computed(() => buildApiUrl(
    config.public.apiBaseUrl,
    `/polygons/by-slug/${encodeURIComponent(data.value.slug)}/preview.webp?width=1200&height=630`
  ))
  const imageAlt = computed(() => `Kartenansicht der Fläche „${data.value.name}“ mit Lage und öffentlichen Flächendaten im Stadtplaner Flensburg`)
  const structuredData = computed(() => [
    {
      '@context': 'https://schema.org',
      '@type': 'Place',
      '@id': `${url.value}#place`,
      name: data.value.name,
      description: description.value,
      url: url.value,
      geo: {
        '@type': 'GeoCoordinates',
        latitude: data.value.centroid[1],
        longitude: data.value.centroid[0]
      }
    },
    buildBreadcrumbStructuredData(config.public.siteUrl, [
      { name: 'Karte', path: '/karte' },
      { name: data.value.name, path: path.value }
    ])
  ])

  useSeoMeta({
    title: () => title.value,
    description: () => description.value,
    robots: 'index,follow',
    ogTitle: () => title.value,
    ogDescription: () => description.value,
    ogType: 'website',
    ogUrl: () => url.value,
    ogSiteName: config.public.siteName,
    ogLocale: config.public.siteLocale,
    ogImage: () => image.value,
    ogImageAlt: () => imageAlt.value,
    ogImageWidth: 1200,
    ogImageHeight: 630,
    twitterCard: 'summary_large_image',
    twitterTitle: () => title.value,
    twitterDescription: () => description.value,
    twitterImage: () => image.value,
    twitterImageAlt: () => imageAlt.value
  })
  useHead(() => ({
    link: [{ rel: 'canonical', href: url.value }],
    script: [{ type: 'application/ld+json', innerHTML: serializeStructuredData(structuredData.value) }]
  }))
}
