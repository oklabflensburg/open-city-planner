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
  path: '/karte',
  structuredData: {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    applicationCategory: 'GISApplication',
    operatingSystem: 'Web',
    name: 'Interaktive Stadtkarte',
    url: buildAbsoluteUrl(config.public.siteUrl, '/karte'),
    description
  }
})
</script>
