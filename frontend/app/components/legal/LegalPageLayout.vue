<template>
  <ContentPageShell
    :title="title"
    :description="intro"
    eyebrow="Rechtliches"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: title }]"
    max-width="reading"
  >
    <Card class="space-y-8 p-5 sm:p-7"><slot /></Card>
  </ContentPageShell>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  intro?: string
}>()
</script>
