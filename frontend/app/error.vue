<template>
  <NuxtLayout>
    <div class="mx-auto max-w-3xl px-5 py-16 sm:px-6 lg:px-8">
      <p class="text-sm font-bold text-[#687176]">Fehler {{ error.statusCode }}</p>
      <h1 class="mt-2 text-3xl font-bold text-[#202427]">{{ title }}</h1>
      <p class="mt-4 text-[#4f575c]">{{ error.statusMessage || 'Die angeforderte Seite konnte nicht geladen werden.' }}</p>
      <NuxtLink class="page-button-primary mt-6" to="/karte">Zur Karte</NuxtLink>
    </div>
  </NuxtLayout>
</template>

<script setup lang="ts">
const props = defineProps<{ error: { statusCode: number; statusMessage?: string } }>()
const title = computed(() => props.error.statusCode === 404 ? 'Seite nicht gefunden' : 'Ein Fehler ist aufgetreten')

useSeoMeta({
  title: () => `${title.value} – OK Lab Flensburg`,
  robots: 'noindex,nofollow'
})
</script>
