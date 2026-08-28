<template>
  <ContentPageShell
    title="Frontend-Modulbeispiel"
    description="Diese serverseitig gerenderte Seite demonstriert die Build-Time-Integration eines lokalen Nuxt Layers."
    eyebrow="Architekturbeispiel"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Frontend-Modulbeispiel' }]"
  >
    <ExampleModuleCard />
  </ContentPageShell>
</template>

<script setup lang="ts">
import ExampleModuleCard from '../components/ExampleModuleCard.vue'
import { useModuleSeo } from '#frontend-module-sdk'

useModuleSeo({
  title: 'Frontend-Modulbeispiel',
  description: 'Build-Time-Modul mit gemeinsamem SSR, SEO, Tailwind und Pinia.',
  path: '/module-example',
  robots: 'noindex,nofollow',
  structuredData: false
})
</script>
