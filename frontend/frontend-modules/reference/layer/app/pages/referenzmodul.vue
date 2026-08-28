<template>
  <ContentPageShell
    title="Referenzmodul"
    description="Ein kleines End-to-End-Modul als ausführbare Dokumentation für das öffentliche Module SDK."
    eyebrow="Module SDK"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Referenzmodul' }]"
  >
    <ReferenceItemList
      :items="data ?? []"
      :pending="pending"
      :error="Boolean(error)"
    />
  </ContentPageShell>
</template>

<script setup lang="ts">
import ReferenceItemList from '../components/ReferenceItemList.vue'
import { useReferenceItems } from '../composables/useReferenceItems'
import { useModuleSeo } from '#frontend-module-sdk'

const { data, pending, error } = useReferenceItems()

useModuleSeo({
  title: 'Referenzmodul',
  description: 'Ausführbares End-to-End-Beispiel für das Open City Planner Module SDK.',
  path: '/referenzmodul',
  robots: 'noindex,nofollow',
  structuredData: false
})
</script>
