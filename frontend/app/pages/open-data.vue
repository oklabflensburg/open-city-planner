<template>
  <article class="mx-auto max-w-3xl px-5 py-12 sm:px-6 lg:px-8">
    <p class="mb-3 text-xs font-bold uppercase text-[#687176]">Projekt</p>
    <h1 class="text-3xl font-bold text-[#202427]">Open Data</h1>
    <div class="mt-8 rounded-lg border border-[#e2e4e5] bg-white p-6 text-sm leading-6 text-[#4f575c] shadow-[0_1px_12px_rgba(20,24,28,0.06)]">
      <p>
        Die Anwendung ist für offene Geodaten, transparente Stadtanalysen und nachvollziehbare digitale Werkzeuge ausgelegt.
      </p>
      <p class="mt-4">
        Konkrete Datenquellen, Lizenzen und Aktualisierungsprozesse müssen vom Betreiber für den Produktivbetrieb ergänzt werden.
      </p>
    </div>
  </article>
</template>

<script setup lang="ts">
import { buildWebPageStructuredData } from '~/utils/seo'

const config = useRuntimeConfig()
const description = 'Hinweise zu offenen Geodaten, Datenquellen und transparenter Stadtanalyse in der Open City Map.'
usePageSeo({
  title: 'Open Data',
  description,
  path: '/open-data',
  structuredData: buildWebPageStructuredData(config.public.siteUrl, '/open-data', 'Open Data', description)
})
</script>
