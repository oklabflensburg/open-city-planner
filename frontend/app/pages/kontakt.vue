<template>
  <ContentPageShell title="Kontakt" :description="description" eyebrow="Kontakt" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Kontakt' }]" max-width="reading">
    <Card class="p-5 sm:p-7">
      <div v-if="success" class="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-950" role="status" aria-live="polite">
        <div class="flex gap-3">
          <CircleCheck class="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <div>
            <h2 class="font-bold">Nachricht gesendet</h2>
            <p class="mt-1 text-sm leading-6">Vielen Dank. Ihre Nachricht wurde an das Stadtplaner-Team übermittelt.</p>
            <p class="mt-1 text-sm leading-6">{{ success.copySent ? 'Eine Kopie wurde an Ihre E-Mail-Adresse gesendet.' : 'Die Kopie konnte leider nicht zugestellt werden.' }}</p>
          </div>
        </div>
      </div>

      <form novalidate @submit.prevent="submit">
        <div class="grid gap-5">
          <label class="grid gap-1.5 text-sm font-semibold text-slate-700" for="contact-name">
            Name
            <input id="contact-name" v-model="fields.name" class="field-input" autocomplete="name" maxlength="120" required :aria-invalid="!!errors.name" :aria-describedby="errors.name ? 'contact-name-error' : undefined" @blur="validateField('name')">
            <span v-if="errors.name" id="contact-name-error" class="text-sm font-semibold text-rose-700">{{ errors.name }}</span>
          </label>

          <label class="grid gap-1.5 text-sm font-semibold text-slate-700" for="contact-email">
            E-Mail-Adresse
            <input id="contact-email" v-model="fields.email" class="field-input" type="email" autocomplete="email" maxlength="320" required :aria-invalid="!!errors.email" :aria-describedby="errors.email ? 'contact-email-error' : undefined" @blur="validateField('email')">
            <span v-if="errors.email" id="contact-email-error" class="text-sm font-semibold text-rose-700">{{ errors.email }}</span>
          </label>

          <label class="grid gap-1.5 text-sm font-semibold text-slate-700" for="contact-subject">
            Betreff
            <input id="contact-subject" v-model="fields.subject" class="field-input" autocomplete="off" maxlength="160" required :aria-invalid="!!errors.subject" :aria-describedby="errors.subject ? 'contact-subject-error' : undefined" @blur="validateField('subject')">
            <span v-if="errors.subject" id="contact-subject-error" class="text-sm font-semibold text-rose-700">{{ errors.subject }}</span>
          </label>

          <label class="grid gap-1.5 text-sm font-semibold text-slate-700" for="contact-message">
            Nachricht
            <textarea id="contact-message" v-model="fields.message" class="field-input min-h-44 resize-y" maxlength="5000" required :aria-invalid="!!errors.message" aria-describedby="contact-message-help contact-message-error" @blur="validateField('message')" />
            <span id="contact-message-help" class="flex justify-between gap-3 text-xs font-normal text-slate-500"><span>Mindestens 10 Zeichen</span><span>{{ fields.message.length }}/5000</span></span>
            <span v-if="errors.message" id="contact-message-error" class="text-sm font-semibold text-rose-700">{{ errors.message }}</span>
          </label>

          <div class="contact-honeypot" aria-hidden="true">
            <label for="contact-website">Website</label>
            <input id="contact-website" v-model="website" type="text" name="website" autocomplete="off" tabindex="-1">
          </div>

          <ContactTurnstile v-if="turnstileEnabled && turnstileSiteKey" :key="turnstileKey" :site-key="turnstileSiteKey" @update:token="turnstileToken = $event" />

          <p v-if="submitError" class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800" role="alert">{{ submitError }}</p>
          <p v-if="tokenError" class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-900" role="alert">{{ tokenError }}</p>

          <button class="page-button-primary w-full sm:w-fit disabled:cursor-not-allowed disabled:opacity-50" type="submit" :disabled="submitting || tokenLoading || !formToken || (turnstileEnabled && !turnstileToken)">
            <LoaderCircle v-if="submitting" class="size-4 animate-spin" aria-hidden="true" />
            <Send v-else class="size-4" aria-hidden="true" />
            {{ submitting ? 'Wird gesendet …' : 'Nachricht senden' }}
          </button>
        </div>
      </form>

      <div class="mt-6 border-t border-slate-200 pt-5 text-sm leading-6 text-slate-600">
        <p>Sie erhalten automatisch eine Kopie Ihrer Nachricht per E-Mail.</p>
        <p class="mt-2">Informationen zur Verarbeitung Ihrer Angaben finden Sie in unserer <NuxtLink class="font-bold text-[#154d73] hover:underline" to="/datenschutz">Datenschutzerklärung</NuxtLink>.</p>
      </div>
    </Card>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { CircleCheck, LoaderCircle, Send } from '@lucide/vue'
import { buildWebPageStructuredData } from '~/utils/seo'
import { contactFieldErrors, contactFormSchema, type ContactFormFields } from '~/utils/contact'

type ContactTokenResponse = { form_token: string, turnstile_enabled: boolean, turnstile_site_key?: string | null }
type ContactResponse = { status: 'sent', copy_sent: boolean }

const config = useRuntimeConfig()
const { request } = useApi()
const description = 'Fragen, Hinweise oder Anmerkungen zum Stadtplaner können Sie direkt über das Kontaktformular an das OK Lab Flensburg senden.'
const fields = reactive<ContactFormFields>({ name: '', email: '', subject: '', message: '' })
const errors = reactive<Partial<Record<keyof ContactFormFields, string>>>({})
const website = ref('')
const formToken = ref('')
const tokenLoading = ref(true)
const tokenError = ref('')
const turnstileEnabled = ref(false)
const turnstileSiteKey = ref('')
const turnstileToken = ref('')
const turnstileKey = ref(0)
const submitting = ref(false)
const submitError = ref('')
const success = ref<{ copySent: boolean } | null>(null)

async function loadFormToken() {
  tokenLoading.value = true
  tokenError.value = ''
  try {
    const result = await request<ContactTokenResponse>('/contact/form-token', { retryOnUnauthorized: false })
    formToken.value = result.form_token
    turnstileEnabled.value = result.turnstile_enabled
    turnstileSiteKey.value = result.turnstile_site_key || ''
  } catch {
    tokenError.value = 'Das Kontaktformular konnte nicht vorbereitet werden. Bitte laden Sie die Seite neu.'
  } finally {
    tokenLoading.value = false
  }
}

function validateField(field: keyof ContactFormFields) {
  const current = contactFieldErrors(fields)
  errors[field] = current[field]
}

async function submit() {
  if (submitting.value) return
  Object.assign(errors, { name: undefined, email: undefined, subject: undefined, message: undefined }, contactFieldErrors(fields))
  const parsed = contactFormSchema.safeParse(fields)
  if (!parsed.success || !formToken.value) return
  submitting.value = true
  submitError.value = ''
  success.value = null
  try {
    const response = await request<ContactResponse>('/contact', {
      method: 'POST',
      retryOnUnauthorized: false,
      body: JSON.stringify({
        ...parsed.data,
        website: website.value,
        form_token: formToken.value,
        turnstile_token: turnstileToken.value || null
      })
    })
    success.value = { copySent: response.copy_sent }
    Object.assign(fields, { name: '', email: '', subject: '', message: '' })
    website.value = ''
    turnstileToken.value = ''
    turnstileKey.value += 1
    await loadFormToken()
  } catch (cause) {
    const code = typeof cause === 'object' && cause && 'code' in cause ? String(cause.code) : ''
    submitError.value = ({
      CONTACT_RATE_LIMITED: 'Zu viele Nachrichten in kurzer Zeit. Bitte versuchen Sie es später erneut.',
      CONTACT_VALIDATION_FAILED: 'Bitte prüfen Sie die eingegebenen Kontaktdaten.',
      CONTACT_FORM_TOKEN_INVALID: 'Das Kontaktformular ist abgelaufen. Bitte laden Sie die Seite neu.',
      CONTACT_SPAM_REJECTED: 'Die Nachricht konnte nicht verarbeitet werden. Bitte prüfen Sie Ihre Angaben.',
      CONTACT_SEND_FAILED: 'Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es später erneut.'
    }[code] || 'Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es erneut.')
    if (code === 'CONTACT_FORM_TOKEN_INVALID') await loadFormToken()
  } finally {
    submitting.value = false
  }
}

onMounted(loadFormToken)

usePageSeo({
  title: 'Kontakt',
  description,
  path: '/kontakt',
  structuredData: buildWebPageStructuredData(config.public.siteUrl, '/kontakt', 'Kontakt', description)
})
</script>

<style scoped>
.contact-honeypot {
  position: absolute;
  left: -10000px;
  width: 1px;
  height: 1px;
  overflow: hidden;
}
</style>
