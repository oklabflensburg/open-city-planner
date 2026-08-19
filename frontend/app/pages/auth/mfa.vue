<template>
  <AuthPageShell label="Zwei-Faktor-Authentifizierung">
    <AuthCard eyebrow="Konto" title="Anmeldung bestätigen">
      <p class="mb-5 text-sm leading-6 text-slate-600">Bestätigen Sie die externe Anmeldung mit einem Passkey oder einer anderen eingerichteten Sicherheitsmethode.</p>
      <form v-if="ready" class="grid gap-4" @submit.prevent="submit">
        <button v-if="passkeySupported && hasPasskeyMethod" class="page-button-primary" type="button" :disabled="passkeyLoading" @click="submitPasskey">
          {{ passkeyLoading ? 'Passkey wird geprüft …' : 'Passkey verwenden' }}
        </button>
        <div v-if="hasPasskeyMethod && hasTotpMethod" class="flex items-center gap-3 text-xs font-semibold uppercase tracking-wider text-slate-400"><span class="h-px flex-1 bg-slate-200" /><span>oder</span><span class="h-px flex-1 bg-slate-200" /></div>
        <OtpInput v-if="hasTotpMethod && !useRecovery" ref="otpInput" v-model="code" :disabled="loading" :invalid="Boolean(error)" described-by="mfa-error" />
        <div v-else-if="hasTotpMethod" class="grid gap-2">
          <FormField id="oauth-recovery-code" v-model="recoveryCode" label="Wiederherstellungscode" autocomplete="one-time-code" required :disabled="loading" />
          <p class="text-xs text-slate-500">Geben Sie einen Ihrer zwölfstelligen Codes ein, zum Beispiel ABCD-EFGH-JKLM.</p>
        </div>
        <p v-if="error" id="mfa-error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>
        <button v-if="hasTotpMethod" class="page-button-secondary" type="submit" :disabled="loading || (useRecovery ? !recoveryCodeValid : code.length !== 6)">{{ loading ? 'Wird geprüft …' : 'Authenticator-Code bestätigen' }}</button>
        <button v-if="hasTotpMethod" class="text-sm font-semibold text-[#154d73]" type="button" @click="useRecovery = !useRecovery">{{ useRecovery ? 'Authenticator-Code verwenden' : 'Wiederherstellungscode verwenden' }}</button>
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
import { isPasskeySupported } from '~/utils/webauthn'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const code = ref('')
const recoveryCode = ref('')
const useRecovery = ref(false)
const passkeySupported = ref(false)
const passkeyLoading = ref(false)
const loading = ref(false)
const error = ref('')
const ready = ref(false)
const otpInput = ref<{ focus: () => void } | null>(null)
const redirectTarget = sanitizeInternalRedirect(route.query.redirect)
const recoveryCodeValid = computed(() => /^[A-Z0-9]{12}$/i.test(recoveryCode.value.replace(/[\s-]/g, '')))
const hasPasskeyMethod = computed(() => authStore.mfaChallenge?.methods.includes('passkey') ?? false)
const hasTotpMethod = computed(() => authStore.mfaChallenge?.methods.includes('totp') ?? false)

onMounted(async () => {
  passkeySupported.value = isPasskeySupported()
  const challenge = typeof route.query.challenge === 'string' ? route.query.challenge : ''
  if (!challenge) return
  const requestedMethods = typeof route.query.methods === 'string'
    ? route.query.methods.split(',').filter((value): value is 'passkey' | 'totp' | 'recovery_code' => ['passkey', 'totp', 'recovery_code'].includes(value))
    : ['totp', 'recovery_code'] as const
  authStore.setMfaChallenge(challenge, 300, [...requestedMethods])
  ready.value = true
  await router.replace({ path: '/auth/mfa' })
  await nextTick(() => otpInput.value?.focus())
})

async function submitPasskey() {
  passkeyLoading.value = true
  error.value = ''
  try {
    await authStore.verifyMfaWithPasskey()
    await router.replace(redirectTarget)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Der Passkey konnte nicht geprüft werden.'
  } finally {
    passkeyLoading.value = false
  }
}

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
