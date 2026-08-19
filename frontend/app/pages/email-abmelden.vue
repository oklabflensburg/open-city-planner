<template>
  <ContentPageShell title="Newsletter abbestellen" description="Freiwillige Projektinformationen können mit einem Schritt abbestellt werden." eyebrow="E-Mail-Einstellungen" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Newsletter abbestellen' }]">
    <Card class="mx-auto max-w-xl p-6 text-center"><div v-if="loading" class="h-24 animate-pulse rounded-xl bg-slate-100" /><template v-else><h2 class="text-xl font-bold text-slate-950">{{ title }}</h2><p class="mt-3 text-sm leading-6 text-slate-600">{{ message }}</p><NuxtLink class="page-button-secondary mt-5 inline-flex" to="/profil#benachrichtigungen">Benachrichtigungseinstellungen öffnen</NuxtLink></template></Card>
  </ContentPageShell>
</template>

<script setup lang="ts">
const route = useRoute()
const api = useApi()
const loading = ref(true)
const title = ref('Abmeldung abgeschlossen')
const message = ref('Sie erhalten künftig keine freiwilligen Newsletter-E-Mails mehr.')
onMounted(async () => {
  const token = String(route.query.token || '')
  if (token.length >= 20) {
    try {
      const result = await api.request<{ message: string }>(`/email/unsubscribe?token=${encodeURIComponent(token)}`, { method: 'POST' })
      message.value = result.message
    } catch {
      title.value = 'Abmeldung konnte nicht verarbeitet werden'
      message.value = 'Der Link ist ungültig oder nicht mehr verfügbar.'
    }
  } else {
    title.value = 'Abmeldelink ungültig'
    message.value = 'Der Abmeldelink ist unvollständig.'
  }
  loading.value = false
})
usePageSeo({ title: 'Newsletter abbestellen', description: 'Freiwillige Newsletter-E-Mails abbestellen.', path: '/email-abmelden', robots: 'noindex,nofollow', structuredData: false })
</script>
