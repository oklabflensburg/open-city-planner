<template>
  <article class="mx-auto max-w-3xl px-5 py-12 sm:px-6 lg:px-8">
    <p class="mb-3 text-xs font-bold uppercase text-[#687176]">Kontakt</p>
    <h1 class="text-3xl font-bold text-[#202427]">Kontakt</h1>
    <div class="mt-8 rounded-lg border border-[#e2e4e5] bg-white p-6 text-sm leading-6 text-[#4f575c] shadow-[0_1px_12px_rgba(20,24,28,0.06)]">
      <p>
        Kontaktangaben wurden im Repository nicht gefunden. Der Betreiber muss hier vor Veröffentlichung eine geeignete Kontaktmöglichkeit ergänzen.
      </p>
    </div>
  </article>
</template>

<script setup lang="ts">
import { buildWebPageStructuredData } from '~/utils/seo'

const config = useRuntimeConfig()
const description = 'Kontaktmöglichkeiten zur Open City Map und zum OK Lab Flensburg.'
usePageSeo({
  title: 'Kontakt',
  description,
  path: '/kontakt',
  structuredData: buildWebPageStructuredData(config.public.siteUrl, '/kontakt', 'Kontakt', description)
})
</script>
