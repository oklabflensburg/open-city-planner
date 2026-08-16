import type { AnalysisAreaDetail } from '~/types/analysisArea'
import { buildAbsoluteUrl, buildBreadcrumbStructuredData, serializeStructuredData, toMetaDescription } from '~/utils/seo'

export function useAnalysisAreaSeo(area: MaybeRefOrGetter<AnalysisAreaDetail>) {
  const config = useRuntimeConfig()
  const data = computed(() => toValue(area))
  const path = computed(() => `/gebiete/${data.value.slug}`)
  const url = computed(() => buildAbsoluteUrl(config.public.siteUrl, path.value))
  const typeLabel = computed(() => ({ MUNICIPALITY: 'Gemeinde', DISTRICT: 'Stadtteil', QUARTER: 'Quartier' })[data.value.area_type])
  const title = computed(() => data.value.area_type === 'MUNICIPALITY'
    ? `${data.value.name} – Einzelhandel & Standortdaten | Stadtplaner`
    : data.value.area_type === 'DISTRICT'
      ? `${data.value.name} Flensburg – Standortanalyse | Stadtplaner`
      : `${data.value.name} – Standortdaten im Quartier | Stadtplaner Flensburg`)
  const description = computed(() => toMetaDescription('', `Statistische Kennzahlen, Standort- und Einzelhandelsdaten für ${data.value.name}: Verkaufsflächen, Leerstand, Branchen, Bevölkerung und POIs.`))
  const breadcrumbItems = computed(() => [
    { name: 'Start', path: '/' },
    { name: 'Gebiete', path: '/gebiete' },
    ...(data.value.municipality && data.value.municipality.id !== data.value.parent?.id ? [{ name: data.value.municipality.name, path: `/gebiete/${data.value.municipality.slug}` }] : []),
    ...(data.value.parent ? [{ name: data.value.parent.name, path: `/gebiete/${data.value.parent.slug}` }] : []),
    { name: data.value.name, path: path.value }
  ])
  const structuredData = computed(() => [
    {
      '@context': 'https://schema.org',
      '@type': 'AdministrativeArea',
      '@id': `${url.value}#area`,
      name: data.value.name,
      description: description.value,
      url: url.value,
      additionalType: typeLabel.value,
      ...(data.value.parent ? { containedInPlace: { '@type': 'AdministrativeArea', name: data.value.parent.name, url: buildAbsoluteUrl(config.public.siteUrl, `/gebiete/${data.value.parent.slug}`) } } : {}),
      geo: { '@type': 'GeoCoordinates', longitude: data.value.centroid[0], latitude: data.value.centroid[1] }
    },
    buildBreadcrumbStructuredData(config.public.siteUrl, breadcrumbItems.value)
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
    twitterCard: 'summary',
    twitterTitle: () => title.value,
    twitterDescription: () => description.value
  })
  useHead(() => ({
    link: [{ rel: 'canonical', href: url.value }],
    script: [{ type: 'application/ld+json', innerHTML: serializeStructuredData(structuredData.value) }]
  }))
}
