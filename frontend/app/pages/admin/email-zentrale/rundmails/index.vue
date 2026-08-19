<template>
  <ContentPageShell v-if="authorized" title="E-Mail-Zentrale" description="Rundmails als Entwurf vorbereiten, prüfen und kontrolliert versenden." eyebrow="Administration" :breadcrumbs="[{ label: 'Administration', to: '/admin/benutzer' }, { label: 'E-Mail-Zentrale' }, { label: 'Rundmails' }]" max-width="wide">
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>
    <EmailCenterTabs />
    <div class="mb-5 flex justify-end"><NuxtLink class="page-button-primary" to="/admin/email-zentrale/rundmails/neu">Neue Rundmail</NuxtLink></div>
    <p v-if="error" class="rounded-xl bg-rose-50 p-4 text-rose-800" role="alert">{{ error }}</p>
    <div class="grid gap-4">
      <Card v-for="item in campaigns" :key="item.id" class="grid gap-3 p-5 md:grid-cols-[1fr_auto] md:items-center">
        <div><div class="flex flex-wrap gap-2"><h2 class="font-bold text-slate-950">{{ item.internal_name }}</h2><StatusBadge :tone="item.status === 'DRAFT' ? 'neutral' : item.status === 'COMPLETED' ? 'success' : 'warning'">{{ statusLabel(item.status) }}</StatusBadge></div><p class="mt-1 text-sm text-slate-600">{{ typeLabel(item.campaign_type) }} · {{ item.subject }}</p></div>
        <NuxtLink class="page-button-secondary text-center" :to="`/admin/email-zentrale/rundmails/${item.id}`">Öffnen</NuxtLink>
      </Card>
      <Card v-if="!loading && !campaigns.length" class="p-8 text-center text-slate-600">Noch keine Rundmail vorhanden.</Card>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { EmailCampaign, EmailCampaignStatus, EmailCampaignType } from '~/types/admin'
definePageMeta({ middleware: 'superuser' })
const auth = useAuthStore(); const router = useRouter(); const api = useEmailCampaigns()
const authorized = ref(false); const loading = ref(true); const error = ref(''); const campaigns = ref<EmailCampaign[]>([])
const statusLabel = (value: EmailCampaignStatus) => ({ DRAFT: 'ENTWURF', SCHEDULED: 'GEPLANT', PROCESSING: 'VERSAND', COMPLETED: 'ABGESCHLOSSEN', CANCELLED: 'ABGEBROCHEN' }[value])
const typeLabel = (value: EmailCampaignType) => ({ LEGAL: 'Notwendige Mitteilung', SERVICE: 'Service', NEWSLETTER: 'Newsletter', SYSTEM: 'System' }[value])
onMounted(async () => { if (!auth.initialized) await auth.initialize(); if (!auth.user?.is_superuser) return router.replace('/'); authorized.value = true; try { campaigns.value = await api.list() } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Rundmails konnten nicht geladen werden.' } finally { loading.value = false } })
usePageSeo({ title: 'Rundmails', description: 'Rundmails verwalten.', path: '/admin/email-zentrale/rundmails', robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
