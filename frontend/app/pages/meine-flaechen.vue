<template>
  <ContentPageShell title="Meine Flächen" description="Von Ihnen angelegte Flächen ansehen und weiter bearbeiten." eyebrow="Flächenverwaltung" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Meine Flächen' }]" max-width="content">
    <template #actions>
      <div class="flex min-w-0 items-center gap-3 rounded-md border border-[#dfe4e6] bg-white px-3 py-2">
        <UserAvatar :user="authStore.user" size="sm" />
        <div class="min-w-0">
          <p class="truncate text-sm font-bold text-[#202427]">{{ authStore.displayName }}</p>
          <p class="truncate text-xs text-[#687176]">Eigene Einträge</p>
        </div>
      </div>
    </template>
    <Card class="overflow-hidden">
      <div v-if="loading" class="space-y-3 p-6" aria-live="polite" aria-label="Flächen werden geladen">
        <div v-for="item in 3" :key="item" class="h-12 animate-pulse rounded-xl bg-slate-100" />
      </div>
      <div v-else-if="error" class="p-6 text-center">
        <p class="font-semibold text-slate-950">Flächen konnten nicht geladen werden.</p>
        <p class="mt-2 text-sm text-slate-600">{{ error }}</p>
        <button class="page-button-secondary mt-4" type="button" @click="loadPolygons">Erneut versuchen</button>
      </div>
      <div v-else-if="!polygons.length" class="p-8 text-center sm:p-10">
        <h2 class="text-lg font-bold text-slate-950">Noch keine eigenen Flächen</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">Zeichnen Sie Ihre erste Fläche direkt auf der Karte.</p>
        <NuxtLink class="page-button-primary mt-5" to="/flaechen/neu">Neue Fläche anlegen</NuxtLink>
      </div>
      <div v-else class="overflow-x-auto">
      <table class="min-w-[720px] w-full text-left text-sm">
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
        </tbody>
      </table>
      </div>
    </Card>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { polygonSchema } from '~/utils/validation'
import type { UserPolygon } from '~/types/geo'

definePageMeta({ middleware: 'auth' })
const { request } = useApi()
const authStore = useAuthStore()
const polygons = ref<UserPolygon[]>([])
const loading = ref(true)
const error = ref('')

async function loadPolygons() {
  loading.value = true
  error.value = ''
  try {
    const result = await request<unknown[]>('/users/me/polygons')
    polygons.value = result.map((item) => polygonSchema.parse(item))
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Bitte versuchen Sie es erneut.'
  } finally {
    loading.value = false
  }
}

onMounted(loadPolygons)

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
