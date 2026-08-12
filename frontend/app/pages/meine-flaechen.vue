<template>
  <main class="mx-auto max-w-5xl px-5 py-12 sm:px-6 lg:px-8">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <h1 class="text-3xl font-bold text-[#202427]">Meine Flächen</h1>
      <div class="flex min-w-0 items-center gap-3 rounded-md border border-[#dfe4e6] bg-white px-3 py-2">
        <UserAvatar :user="authStore.user" size="sm" />
        <div class="min-w-0">
          <p class="truncate text-sm font-bold text-[#202427]">{{ authStore.displayName }}</p>
          <p class="truncate text-xs text-[#687176]">Eigene Einträge</p>
        </div>
      </div>
    </div>
    <section class="mt-8 overflow-hidden rounded-lg border border-[#dfe4e6] bg-white">
      <table class="w-full text-left text-sm">
        <thead class="bg-[#eef2f3] text-xs uppercase text-[#687176]">
          <tr>
            <th class="px-4 py-3">Name</th>
            <th class="px-4 py-3">Kategorie</th>
            <th class="px-4 py-3">Erstellt</th>
            <th class="px-4 py-3">Aktualisiert</th>
            <th class="px-4 py-3 text-right">Aktion</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="polygon in polygons" :key="polygon.id" class="border-t border-[#edf0f1]">
            <td class="px-4 py-3 font-semibold">{{ polygon.name }}</td>
            <td class="px-4 py-3">{{ polygon.category }}</td>
            <td class="px-4 py-3">{{ formatDate(polygon.created_at) }}</td>
            <td class="px-4 py-3">{{ formatDate(polygon.updated_at) }}</td>
            <td class="px-4 py-3 text-right"><NuxtLink class="font-semibold text-[#154d73]" :to="`/flaechen/${polygon.slug}`">Details anzeigen</NuxtLink></td>
          </tr>
          <tr v-if="!polygons.length">
            <td class="px-4 py-6 text-[#687176]" colspan="5">Noch keine eigenen Flächen vorhanden.</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { polygonSchema } from '~/utils/validation'
import type { UserPolygon } from '~/types/geo'

definePageMeta({ middleware: 'auth' })
const { request } = useApi()
const authStore = useAuthStore()
const polygons = ref<UserPolygon[]>([])

onMounted(async () => {
  const result = await request<unknown[]>('/users/me/polygons')
  polygons.value = result.map((item) => polygonSchema.parse(item))
})

function formatDate(value: string) {
  return new Intl.DateTimeFormat('de-DE').format(new Date(value))
}

usePageSeo({
  title: 'Meine Flächen',
  description: 'Verwalte die von dir angelegten Flächen.',
  path: '/meine-flaechen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
