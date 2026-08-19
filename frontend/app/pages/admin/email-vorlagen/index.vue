<template>
  <ContentPageShell
    v-if="authorized"
    title="E-Mail-Zentrale"
    description="Systemmails zentral verwalten, ihren Einsatz prüfen und sichere Standardinhalte wiederherstellen."
    eyebrow="Administration"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Administration', to: '/admin/benutzer' }, { label: 'E-Mail-Vorlagen' }]"
    max-width="wide"
  >
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>
    <EmailCenterTabs />

    <p v-if="error" class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
    <div v-if="loading" class="grid gap-4 md:grid-cols-2" role="status" aria-label="E-Mail-Vorlagen werden geladen">
      <div v-for="index in 6" :key="index" class="h-40 animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
    <div v-else class="grid gap-6">
      <section v-for="category in categories" :key="category" :aria-labelledby="`email-category-${category}`">
        <h2 :id="`email-category-${category}`" class="mb-3 text-xl font-bold text-slate-950">{{ category }}</h2>
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Card v-for="item in grouped[category]" :key="item.key" class="flex flex-col p-5">
            <div class="flex items-start justify-between gap-3">
              <h3 class="font-bold text-slate-950">{{ item.name }}</h3>
              <StatusBadge :tone="item.customized ? 'warning' : 'neutral'">{{ item.customized ? 'ANGEPASST' : 'STANDARD' }}</StatusBadge>
            </div>
            <p class="mt-2 flex-1 text-sm leading-6 text-slate-600">{{ item.description }}</p>
            <p class="mt-3 text-xs font-semibold text-slate-500">{{ item.active ? 'Aktiv verwendet' : 'Derzeit nicht verwendet' }} · Version {{ item.version }}</p>
            <NuxtLink class="page-button-secondary mt-4 text-center" :to="`/admin/email-vorlagen/${encodeURIComponent(item.key)}`">Vorlage bearbeiten</NuxtLink>
          </Card>
        </div>
      </section>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { EmailTemplateListItem } from '~/types/admin'

definePageMeta({ middleware: 'superuser' })
const authStore = useAuthStore()
const router = useRouter()
const api = useEmailTemplates()
const templates = ref<EmailTemplateListItem[]>([])
const loading = ref(true)
const error = ref('')
const authorized = ref(false)
const categories = ['Sicherheit', 'Konto', 'Kontakt', 'Kommunikation / System'] as const
const grouped = computed(() => Object.fromEntries(
  categories.map(category => [category, templates.value.filter(item => item.category === category)])
) as Record<(typeof categories)[number], EmailTemplateListItem[]>)

onMounted(async () => {
  if (!authStore.initialized) await authStore.initialize()
  if (!authStore.user?.is_superuser) {
    await router.replace('/')
    return
  }
  authorized.value = true
  try { templates.value = await api.list() } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'E-Mail-Vorlagen konnten nicht geladen werden.'
  } finally { loading.value = false }
})

usePageSeo({
  title: 'E-Mail-Vorlagen',
  description: 'Geschützte Verwaltung der Systemmail-Vorlagen.',
  path: '/admin/email-vorlagen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
