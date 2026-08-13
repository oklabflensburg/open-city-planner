<template>
  <ContentPageShell max-width="reading">
    <PageBreadcrumbs :items="[{ label: 'Startseite', to: '/' }, { label }]" />
    <div class="mt-8 sm:mt-10"><slot /></div>
  </ContentPageShell>
</template>

<script setup lang="ts">
defineProps<{ label: string }>()
</script>
