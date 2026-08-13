<template>
  <ContentPageShell title="Kennzahlen verwalten" description="Hier werden die stadtweiten Kennzahlen gepflegt, die öffentlich in den Fast Facts auf der Karte erscheinen." :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Verwaltung' }, { label: 'Kennzahlen' }]" max-width="reading">
    <template #badge><DocsRoleBadge audience="verwaltung" /></template>
    <template #actions>
      <NuxtLink class="page-button-secondary" to="/">
        Zur Karte
      </NuxtLink>
    </template>

    <Card class="p-5 sm:p-7">
      <FastFactsEditor />
    </Card>
  </ContentPageShell>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'verwaltung' })

usePageSeo({
  title: 'Kennzahlen verwalten',
  description: 'Stadtweite Kennzahlen verwalten.',
  path: '/verwaltung/kennzahlen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
