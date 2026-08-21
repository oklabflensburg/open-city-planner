<template>
  <DeveloperDocsLayout :page="page" />
</template>

<script setup lang="ts">
import { developerDocumentationPages } from '~/config/developerDocumentation'

const page = developerDocumentationPages[0]
if (!page) throw createError({ statusCode: 500, statusMessage: 'Entwicklerdokumentation ist nicht konfiguriert.' })
useDeveloperDocumentationSeo(page)
</script>
