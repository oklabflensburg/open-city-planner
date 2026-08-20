<template>
  <DeveloperDocsLayout v-if="page" :page="page" />
</template>

<script setup lang="ts">
import { findDeveloperDocumentationPage } from '~/config/developerDocumentation'

const route = useRoute()
const slug = computed(() => String(route.params.slug || ''))
const page = computed(() => findDeveloperDocumentationPage(slug.value))

if (!page.value) {
  throw createError({ statusCode: 404, statusMessage: 'Entwicklerdokumentation nicht gefunden.' })
}
useDocumentationSeo(page.value)
</script>
