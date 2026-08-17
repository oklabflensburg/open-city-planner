<template>
  <div>
    <h1 class="sr-only">Interaktive Stadtkarte für Flensburg</h1>
    <AppShell />
  </div>
</template>

<script setup lang="ts">
import { buildAbsoluteUrl } from '~/utils/seo'

const config = useRuntimeConfig()
const description = 'Interaktive GIS-Karte für Verkaufsflächen, offene Daten und Stadtanalyse in Flensburg.'

usePageSeo({
  title: 'Interaktive Stadtkarte',
  description,
  path: '/',
  structuredData: {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${buildAbsoluteUrl(config.public.siteUrl, '/')}#website`,
    name: config.public.siteName,
    url: buildAbsoluteUrl(config.public.siteUrl, '/'),
    description
  }
})
if (useRoute().query['social-preview'] === '1') useSeoMeta({ robots: 'noindex,nofollow' })
</script>
