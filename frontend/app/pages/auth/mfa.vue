<template>
  <AuthPageShell label="Zwei-Faktor-Authentifizierung">
    <AuthCard eyebrow="Konto" title="Anmeldung bestätigen">
      <p class="mb-5 text-sm leading-6 text-slate-600">Bestätigen Sie die externe Anmeldung mit Ihrer Authenticator-App.</p>
      <form v-if="ready" class="grid gap-4" @submit.prevent="submit">
        <OtpInput v-if="!useRecovery" ref="otpInput" v-model="code" :disabled="loading" :invalid="Boolean(error)" described-by="mfa-error" />
        <div v-else class="grid gap-2">
          <FormField id="oauth-recovery-code" v-model="recoveryCode" label="Wiederherstellungscode" autocomplete="one-time-code" required :disabled="loading" />
          <p class="text-xs text-slate-500">Geben Sie einen Ihrer zwölfstelligen Codes ein, zum Beispiel ABCD-EFGH-JKLM.</p>
        </div>
        <p v-if="error" id="mfa-error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>
        <button class="page-button-primary" type="submit" :disabled="loading || (useRecovery ? !recoveryCodeValid : code.length !== 6)">{{ loading ? 'Wird geprüft …' : 'Bestätigen' }}</button>
        <button class="text-sm font-semibold text-[#154d73]" type="button" @click="useRecovery = !useRecovery">{{ useRecovery ? 'Authenticator-Code verwenden' : 'Wiederherstellungscode verwenden' }}</button>
      </form>
      <div v-else>
        <p class="rounded-md bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900" role="alert">{{ error || 'Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.' }}</p>
        <NuxtLink class="page-button-primary mt-4" to="/login">Zur Anmeldung</NuxtLink>
      </div>
    </AuthCard>
  </AuthPageShell>
</template>

<script setup lang="ts">
import { sanitizeInternalRedirect } from '~/utils/redirect'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const code = ref('')
const recoveryCode = ref('')
const useRecovery = ref(false)
const loading = ref(false)
const error = ref('')
const ready = ref(false)
const otpInput = ref<{ focus: () => void } | null>(null)
const redirectTarget = sanitizeInternalRedirect(route.query.redirect)
const recoveryCodeValid = computed(() => /^[A-Z0-9]{12}$/i.test(recoveryCode.value.replace(/[\s-]/g, '')))

onMounted(async () => {
  const challenge = typeof route.query.challenge === 'string' ? route.query.challenge : ''
  if (!challenge) return
  authStore.setMfaChallenge(challenge)
  ready.value = true
  await router.replace({ path: '/auth/mfa' })
  await nextTick(() => otpInput.value?.focus())
})

async function submit() {
  if (useRecovery.value && !recoveryCodeValid.value) {
    error.value = 'Der Wiederherstellungscode muss aus zwölf Buchstaben oder Ziffern bestehen.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await authStore.verifyMfa(useRecovery.value ? recoveryCode.value : code.value, useRecovery.value)
    await router.replace(redirectTarget)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Der Code konnte nicht geprüft werden.'
    if (!authStore.mfaChallenge) ready.value = false
    code.value = ''
  } finally {
    loading.value = false
  }
}

usePageSeo({ title: 'Zwei-Faktor-Authentifizierung', description: 'Anmeldung bestätigen.', path: '/auth/mfa', robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
