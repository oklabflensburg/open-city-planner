<template>
  <ContentPageShell v-if="authorized" title="E-Mail-Zentrale" description="Fortschritt und Ergebnis gestarteter Rundmail-Versände." eyebrow="Administration" :breadcrumbs="[{ label: 'E-Mail-Zentrale', to: '/admin/email-vorlagen' }, { label: 'Versand' }]" max-width="wide">
    <EmailCenterTabs />
    <p v-if="error" class="mb-4 rounded-xl bg-rose-50 p-4 text-rose-800" role="alert">{{ error }}</p>
    <div class="overflow-x-auto rounded-xl border border-slate-200"><table class="w-full text-left text-sm"><thead class="bg-slate-50"><tr><th class="p-3">Rundmail</th><th class="p-3">Typ</th><th class="p-3">Status</th><th class="p-3">Fortschritt</th><th class="p-3">Fehler</th><th class="p-3">Start</th><th class="p-3">Abgeschlossen</th></tr></thead><tbody><tr v-for="item in deliveries" :key="item.id" class="border-t"><td class="p-3"><NuxtLink class="font-bold text-[#154d73]" :to="`/admin/email-zentrale/rundmails/${item.id}`">{{ item.internal_name }}</NuxtLink></td><td class="p-3">{{ item.campaign_type }}</td><td class="p-3">{{ item.status }}</td><td class="p-3">{{ item.sent_count }} / {{ item.recipient_count }}</td><td class="p-3">{{ item.failed_count }}</td><td class="p-3">{{ formatDate(item.started_at || item.scheduled_at) }}</td><td class="p-3">{{ formatDate(item.completed_at) }}</td></tr></tbody></table></div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { EmailCampaign } from '~/types/admin'
definePageMeta({ middleware: 'superuser' })
const auth = useAuthStore(); const router = useRouter(); const api = useEmailCampaigns(); const authorized = ref(false); const deliveries = ref<EmailCampaign[]>([]); const error = ref('')
const formatDate = (value: string | null) => value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '–'
const refresh = async () => { try { deliveries.value = (await api.list()).filter(item => item.status !== 'DRAFT'); error.value = '' } catch { error.value = 'Der Versandstatus konnte nicht aktualisiert werden.' } }
let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(async () => { if (!auth.initialized) await auth.initialize(); if (!auth.user?.is_superuser) return router.replace('/'); authorized.value = true; await refresh(); refreshTimer = setInterval(refresh, 15_000) })
onUnmounted(() => clearInterval(refreshTimer))
usePageSeo({ title: 'E-Mail-Versand', description: 'Status der Rundmail-Versände.', path: '/admin/email-zentrale/versand', robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
