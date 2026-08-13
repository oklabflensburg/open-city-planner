<template>
  <main class="mx-auto w-full max-w-4xl px-5 py-10 sm:px-6 lg:px-8 lg:py-12">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-xs font-bold uppercase tracking-wide text-[#7b6333]">Nur VERWALTUNG</p>
        <h1 class="mt-2 text-3xl font-bold text-[#202427]">Kennzahlen verwalten</h1>
        <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          Hier werden die stadtweiten Kennzahlen gepflegt, die öffentlich in den Fast Facts auf der Karte erscheinen.
        </p>
      </div>
      <NuxtLink class="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 transition hover:bg-slate-50" to="/">
        Zur Karte
      </NuxtLink>
    </div>

    <Card class="mt-8 p-5 sm:p-7">
      <FastFactsEditor />
    </Card>
  </main>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'verwaltung' })

usePageSeo({
  title: 'Kennzahlen verwalten',
  description: 'Stadtweite Kennzahlen verwalten.',
  path: '/verwaltung/kennzahlen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
