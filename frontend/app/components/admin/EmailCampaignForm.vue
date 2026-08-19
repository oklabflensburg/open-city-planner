<template>
  <form class="grid gap-5" @submit.prevent="$emit('submit')">
    <Card class="grid gap-5 p-5 sm:p-6">
      <div class="grid gap-4 md:grid-cols-2"><label><span class="field-label">Interner Name</span><input v-model="model.internal_name" class="field-input" maxlength="180" required></label><label><span class="field-label">Typ</span><select v-model="model.campaign_type" class="field-input"><option value="LEGAL">LEGAL – notwendige Mitteilung</option><option value="SERVICE">SERVICE</option><option value="NEWSLETTER">NEWSLETTER</option><option value="SYSTEM">SYSTEM</option></select></label></div>
      <label><span class="field-label">Betreff</span><input v-model="model.subject" class="field-input" maxlength="200" required></label>
      <label><span class="field-label">Titel</span><input v-model="model.title" class="field-input" maxlength="200" required></label>
      <label><span class="field-label">Einleitung</span><textarea v-model="model.intro" class="field-input min-h-24" /></label>
      <label><span class="field-label">HTML-Inhalt</span><textarea v-model="model.content_html" class="field-input min-h-52 font-mono text-sm" required /></label>
      <label><span class="field-label">Text-Version</span><textarea v-model="model.content_text" class="field-input min-h-44" required /></label>
      <div class="grid gap-4 md:grid-cols-2"><label><span class="field-label">CTA-Beschriftung</span><input v-model="model.action_label" class="field-input" maxlength="80"></label><label><span class="field-label">CTA-URL</span><input v-model="model.action_url" class="field-input" placeholder="/dokumentation oder https://…"></label></div>
      <div class="grid gap-4 md:grid-cols-2"><label><span class="field-label">Zielgruppe</span><select v-model="model.recipient_scope" class="field-input"><option value="ALL_ACTIVE_USERS">Alle aktiven Benutzer</option><option value="VERIFIED_USERS">Bestätigte Benutzer</option><option value="SUPERUSERS">Superuser</option></select></label><label><span class="field-label">Versandzeitpunkt (optional)</span><input v-model="scheduledLocal" class="field-input" type="datetime-local"></label></div>
    </Card>
    <div><Button variant="primary" type="submit" :disabled="busy">{{ submitLabel }}</Button></div>
  </form>
</template>

<script setup lang="ts">
import type { EmailCampaignWrite } from '~/types/admin'
const model = defineModel<EmailCampaignWrite>({ required: true })
defineProps<{ busy?: boolean, submitLabel: string }>(); defineEmits<{ submit: [] }>()
const scheduledLocal = computed({ get: () => model.value.scheduled_at?.slice(0, 16) || '', set: value => { model.value.scheduled_at = value ? new Date(value).toISOString() : null } })
</script>
