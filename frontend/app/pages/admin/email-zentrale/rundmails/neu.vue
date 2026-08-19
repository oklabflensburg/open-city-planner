<template>
  <ContentPageShell v-if="authorized" title="Neue Rundmail" description="Ein Entwurf versendet niemals automatisch E-Mails." eyebrow="E-Mail-Zentrale" :breadcrumbs="[{ label: 'E-Mail-Zentrale', to: '/admin/email-vorlagen' }, { label: 'Rundmails', to: '/admin/email-zentrale/rundmails' }, { label: 'Neu' }]" max-width="wide">
    <EmailCenterTabs /><EmailCampaignForm v-model="draft" :busy="busy" submit-label="Entwurf speichern" @submit="save" />
    <p v-if="error" class="mt-4 rounded-xl bg-rose-50 p-4 text-rose-800" role="alert">{{ error }}</p>
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { EmailCampaignWrite } from '~/types/admin'
definePageMeta({ middleware: 'superuser' })
const auth = useAuthStore(); const router = useRouter(); const api = useEmailCampaigns(); const authorized = ref(false); const busy = ref(false); const error = ref('')
const draft = ref<EmailCampaignWrite>({ internal_name: '', subject: '', title: '', intro: '', content_html: '<p></p>', content_text: '', action_url: '', action_label: '', campaign_type: 'NEWSLETTER', recipient_scope: 'VERIFIED_USERS', scheduled_at: null, version: 1 })
async function save() { busy.value = true; error.value = ''; try { const item = await api.create(draft.value); await router.push(`/admin/email-zentrale/rundmails/${item.id}`) } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Der Entwurf konnte nicht gespeichert werden.' } finally { busy.value = false } }
onMounted(async () => { if (!auth.initialized) await auth.initialize(); if (!auth.user?.is_superuser) return router.replace('/'); authorized.value = true })
usePageSeo({ title: 'Neue Rundmail', description: 'Eine Rundmail als Entwurf anlegen.', path: '/admin/email-zentrale/rundmails/neu', robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
