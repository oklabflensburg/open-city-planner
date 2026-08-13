<template>
  <DocsLayout :page="page" />
</template>

<script setup lang="ts">
import { findDocumentationPage } from '~/utils/documentation'

const route = useRoute()
const slug = Array.isArray(route.params.slug) ? route.params.slug[0] : route.params.slug
const page = findDocumentationPage(slug)

if (!page) {
  throw createError({ statusCode: 404, statusMessage: 'Dokumentationsseite nicht gefunden.' })
}

useDocumentationSeo(page)
</script>
