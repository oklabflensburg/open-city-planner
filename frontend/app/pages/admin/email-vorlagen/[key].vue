<template>
  <ContentPageShell
    v-if="authorized"
    :title="template?.name || 'E-Mail-Vorlage bearbeiten'"
    description="Betreff und Mailinhalt bearbeiten. Branding, Layout sowie Impressum und Datenschutz werden unveränderlich ergänzt."
    eyebrow="E-Mail-Vorlagen"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Administration', to: '/admin/benutzer' }, { label: 'E-Mail-Vorlagen', to: '/admin/email-vorlagen' }, { label: template?.name || key }]"
    max-width="wide"
  >
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>

    <p v-if="success" class="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900" role="status">{{ success }}</p>
    <p v-if="error" class="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
    <Card v-if="loading" class="h-96 animate-pulse" role="status" aria-label="Vorlage wird geladen" />
    <form v-else-if="template" class="grid gap-5" @submit.prevent="save">
      <Card class="grid gap-5 p-5 sm:p-6">
        <div class="grid gap-4 sm:grid-cols-2">
          <div><span class="field-label">Template-Key</span><code class="block rounded-lg bg-slate-100 px-3 py-2 text-sm">{{ template.key }}</code></div>
          <div><span class="field-label">Status</span><p class="text-sm font-semibold">{{ template.active ? 'Aktiv verwendet' : 'Derzeit nicht verwendet' }} · Version {{ template.version }}</p></div>
        </div>
        <label><span class="field-label">Betreff</span><input v-model="template.subject" class="field-input" maxlength="200" required></label>
        <label><span class="field-label">HTML-Inhalt</span><textarea v-model="template.html_body" class="field-input min-h-64 font-mono text-sm" maxlength="50000" required spellcheck="false" /></label>
        <label><span class="field-label">Text-Version</span><textarea v-model="template.text_body" class="field-input min-h-56 font-mono text-sm" maxlength="50000" required /></label>
      </Card>

      <Card class="p-5 sm:p-6">
        <h2 class="font-bold text-slate-950">Verfügbare Variablen</h2>
        <p class="mt-1 text-sm text-slate-600">Nur diese Werte können verwendet werden. Pflichtvariablen sind gekennzeichnet.</p>
        <div class="mt-3 flex flex-wrap gap-2">
          <code v-for="variable in template.allowed_variables" :key="variable" class="rounded-lg bg-slate-100 px-3 py-2 text-sm">{{ variablePlaceholder(variable) }}<strong v-if="template.required_variables.includes(variable)" class="ml-1 text-rose-700">Pflicht</strong></code>
        </div>
      </Card>

      <div class="flex flex-wrap gap-3">
        <Button variant="primary" type="submit" :disabled="busy">Änderungen speichern</Button>
        <Button :disabled="busy" @click="showPreview">Vorschau</Button>
        <Button :disabled="busy" @click="sendTest">Test-E-Mail senden</Button>
        <Button variant="ghost" :disabled="busy" @click="resetOpen = true">Standard wiederherstellen</Button>
      </div>
    </form>

    <AppModal :open="Boolean(preview)" title="E-Mail-Vorschau" size="xl" @close="preview = null" @update:open="value => { if (!value) preview = null }">
      <template v-if="preview">
        <p class="mb-3 text-sm"><strong>Betreff:</strong> {{ preview.subject }}</p>
        <iframe class="h-[32rem] w-full rounded-xl border border-slate-200 bg-white" title="Gerenderte E-Mail-Vorschau" sandbox="" :srcdoc="preview.html" />
        <details class="mt-4"><summary class="cursor-pointer font-semibold">Text-Version anzeigen</summary><pre class="mt-3 whitespace-pre-wrap rounded-xl bg-slate-100 p-4 text-sm">{{ preview.text }}</pre></details>
      </template>
    </AppModal>
    <AppConfirmDialog
      :open="resetOpen"
      title="Standard wiederherstellen?"
      body="Betreff, HTML- und Text-Inhalt werden auf den im Repository hinterlegten Standard zurückgesetzt."
      confirm-label="Standard wiederherstellen"
      variant="warning"
      :loading="busy"
      @confirm="resetTemplate"
      @cancel="resetOpen = false"
      @update:open="resetOpen = $event"
    />
  </ContentPageShell>
</template>

<script setup lang="ts">
import type { EmailTemplateDetail, EmailTemplatePreview } from '~/types/admin'

definePageMeta({ middleware: 'superuser' })
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const api = useEmailTemplates()
const key = computed(() => String(route.params.key || ''))
const template = ref<EmailTemplateDetail | null>(null)
const preview = ref<EmailTemplatePreview | null>(null)
const loading = ref(true)
const busy = ref(false)
const resetOpen = ref(false)
const error = ref('')
const success = ref('')
const authorized = ref(false)

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback
}

function variablePlaceholder(variable: string) {
  return `{{ ${variable} }}`
}

async function load() {
  loading.value = true
  error.value = ''
  try { template.value = await api.load(key.value) } catch (cause) {
    error.value = message(cause, 'Die E-Mail-Vorlage konnte nicht geladen werden.')
  } finally { loading.value = false }
}

async function act(action: () => Promise<void>) {
  if (!template.value || busy.value) return
  busy.value = true
  error.value = ''
  success.value = ''
  try { await action() } catch (cause) { error.value = message(cause, 'Die Aktion konnte nicht ausgeführt werden.') } finally { busy.value = false }
}

async function save() {
  await act(async () => {
    template.value = await api.save(template.value!)
    success.value = 'Die E-Mail-Vorlage wurde gespeichert.'
  })
}

async function showPreview() {
  await act(async () => { preview.value = await api.preview(template.value!) })
}

async function sendTest() {
  await act(async () => { success.value = (await api.testSend(template.value!)).message })
}

async function resetTemplate() {
  await act(async () => {
    template.value = await api.reset(template.value!)
    resetOpen.value = false
    success.value = 'Der Standard wurde wiederhergestellt.'
  })
}

onMounted(async () => {
  if (!authStore.initialized) await authStore.initialize()
  if (!authStore.user?.is_superuser) {
    await router.replace('/')
    return
  }
  authorized.value = true
  await load()
})
usePageSeo({ title: 'E-Mail-Vorlage bearbeiten', description: 'Geschützter Editor für Systemmails.', path: `/admin/email-vorlagen/${key.value}`, robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
