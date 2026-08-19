<template>
  <AuthPageShell label="Anmelden">
    <ClientOnly>
      <AuthCard eyebrow="Konto" :title="mfaStep ? 'Zwei-Faktor-Authentifizierung' : 'Anmelden'">
      <template v-if="mfaStep">
        <p class="mb-5 text-sm leading-6 text-slate-600">Geben Sie den sechsstelligen Code aus Ihrer Authenticator-App ein.</p>
        <form class="grid gap-4" @submit.prevent="submitMfa">
          <OtpInput v-if="!useRecovery" ref="otpInput" v-model="mfaCode" :disabled="loading" :invalid="Boolean(error)" described-by="mfa-error" />
          <div v-else class="grid gap-2">
            <FormField id="recovery-code" v-model="recoveryCode" label="Wiederherstellungscode" autocomplete="one-time-code" required :disabled="loading" />
            <p class="text-xs text-slate-500">Geben Sie einen Ihrer zwölfstelligen Codes ein, zum Beispiel ABCD-EFGH-JKLM.</p>
          </div>
          <p v-if="error" id="mfa-error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>
          <button class="page-button-primary disabled:opacity-60" type="submit" :disabled="loading || (useRecovery ? !recoveryCodeValid : mfaCode.length !== 6)">{{ loading ? 'Wird geprüft …' : 'Bestätigen' }}</button>
          <button class="text-sm font-semibold text-[#154d73]" type="button" :disabled="loading" @click="toggleRecovery">{{ useRecovery ? 'Authenticator-Code verwenden' : 'Wiederherstellungscode verwenden' }}</button>
          <button class="text-sm font-semibold text-slate-600" type="button" :disabled="loading" @click="backToLogin">Zurück</button>
        </form>
      </template>
      <template v-else>
      <p v-if="accountStatusMessage" class="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-900" role="status">{{ accountStatusMessage }}</p>
      <p v-if="sessionExpired" class="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900" role="status">Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.</p>
      <Card
        v-if="authErrorPresentation"
        class="mb-5 border px-4 py-4"
        :class="authErrorPresentation.accountStatus ? 'border-amber-200 bg-amber-50' : 'border-rose-200 bg-rose-50'"
        role="status"
      >
        <h2 v-if="authErrorPresentation.title" class="font-bold text-slate-950">{{ authErrorPresentation.title }}</h2>
        <p class="text-sm leading-6 text-slate-700" :class="{ 'mt-2': authErrorPresentation.title }">{{ authErrorPresentation.message }}</p>
        <p v-if="authErrorPresentation.showSupportLink" class="mt-2 text-sm leading-6 text-slate-700">Wenn Sie Ihr Konto wieder verwenden möchten, wenden Sie sich bitte an den Support.</p>
        <NuxtLink v-if="authErrorPresentation.showSupportLink" class="page-button-secondary mt-4 w-full sm:w-auto" to="/kontakt">Kontakt aufnehmen</NuxtLink>
      </Card>
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="email" v-model="email" label="E-Mail" type="email" autocomplete="email" required :disabled="loading" />
        <FormField id="password" v-model="password" label="Passwort" type="password" autocomplete="current-password" required :disabled="loading" />
        <label class="flex cursor-pointer items-center gap-2 text-sm text-[#4f575c]">
          <input v-model="remember" class="accent-[#154d73]" type="checkbox">
          Angemeldet bleiben
        </label>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="page-button-primary disabled:opacity-60" type="submit" :disabled="loading">
          Anmelden
        </button>
      </form>
      <OAuthLoginButtons class="mt-5" mode="login" :redirect="redirectTarget" />
      <div class="mt-5 grid gap-2 text-sm">
        <NuxtLink class="font-semibold text-[#154d73]" to="/passwort-vergessen">Passwort vergessen?</NuxtLink>
        <NuxtLink class="font-semibold text-[#154d73]" to="/registrieren">Noch kein Konto? Registrieren</NuxtLink>
      </div>
      </template>
      </AuthCard>
      <template #fallback>
        <div class="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm" role="status">
          <span class="inline-block size-6 animate-spin rounded-full border-2 border-slate-300 border-t-[#154d73]" aria-hidden="true" />
          <p class="mt-3 text-sm font-semibold text-slate-600">Sitzung wird geprüft …</p>
        </div>
      </template>
    </ClientOnly>
  </AuthPageShell>
</template>

<script setup lang="ts">
import { ApiError } from '~/composables/useApi'
import { getAuthErrorPresentation } from '~/utils/authErrors'
import { sanitizeInternalRedirect } from '~/utils/redirect'

definePageMeta({ middleware: 'guest' })
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const email = ref('')
const password = ref('')
const remember = ref(true)
const loading = ref(false)
const error = ref('')
const mfaCode = ref('')
const recoveryCode = ref('')
const useRecovery = ref(false)
const otpInput = ref<{ focus: () => void } | null>(null)
const mfaStep = computed(() => Boolean(authStore.mfaChallenge))
const recoveryCodeValid = computed(() => /^[A-Z0-9]{12}$/i.test(recoveryCode.value.replace(/[\s-]/g, '')))
const authErrorCode = ref(typeof route.query.auth_error === 'string' ? route.query.auth_error : '')
const accountResult = ref(typeof route.query.account === 'string' ? route.query.account : '')
const redirectTarget = computed(() => sanitizeInternalRedirect(route.query.redirect))
const sessionExpired = computed(() => route.query.session_expired === '1')
const accountStatusMessage = computed(() => ({
  deactivated: 'Das Konto wurde deaktiviert. Eine Reaktivierung ist über die Administration möglich.',
  deleted: 'Das Konto wurde dauerhaft gelöscht.'
}[accountResult.value] || ''))
const authErrorPresentation = computed(() => getAuthErrorPresentation(authErrorCode.value))

onMounted(async () => {
  if (!route.query.auth_error && !route.query.account) return
  const query = { ...route.query }
  delete query.auth_error
  delete query.account
  await router.replace({ query })
})

async function submit() {
  loading.value = true
  error.value = ''
  authErrorCode.value = ''
  try {
    const result = await authStore.login({ email: email.value, password: password.value, remember: remember.value })
    if (result.status === 'authenticated') await router.push(redirectTarget.value)
    else await nextTick(() => otpInput.value?.focus())
  } catch (err) {
    if (err instanceof ApiError && getAuthErrorPresentation(err.code)?.accountStatus) {
      authErrorCode.value = err.code || ''
    } else {
      error.value = err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen.'
    }
  } finally {
    loading.value = false
  }
}

async function submitMfa() {
  loading.value = true
  error.value = ''
  try {
    await authStore.verifyMfa(useRecovery.value ? recoveryCode.value : mfaCode.value, useRecovery.value)
    await router.push(redirectTarget.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Der Code konnte nicht geprüft werden.'
    mfaCode.value = ''
    await nextTick(() => otpInput.value?.focus())
  } finally {
    loading.value = false
  }
}

function toggleRecovery() {
  useRecovery.value = !useRecovery.value
  error.value = ''
  nextTick(() => otpInput.value?.focus())
}

function backToLogin() {
  authStore.clearMfaChallenge()
  mfaCode.value = ''
  recoveryCode.value = ''
  error.value = ''
}

usePageSeo({
  title: 'Anmelden',
  description: 'Bei Stadtplaner anmelden.',
  path: '/login',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
