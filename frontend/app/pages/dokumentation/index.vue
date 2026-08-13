<template>
  <DocsLayout :page="page" />
</template>

<script setup lang="ts">
import { documentationPages } from '~/config/documentation'

const page = documentationPages[0]
if (!page) throw createError({ statusCode: 500, statusMessage: 'Dokumentation ist nicht konfiguriert.' })
useDocumentationSeo(page)
</script>
