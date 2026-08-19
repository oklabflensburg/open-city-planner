<template>
  <AuthPageShell label="Anmelden">
    <ClientOnly>
      <AuthCard eyebrow="Konto" :title="mfaStep ? 'Zwei-Faktor-Authentifizierung' : 'Anmelden'">
      <template v-if="mfaStep">
        <MfaChallengeForm
          :redirect-target="redirectTarget"
          @back="backToLogin"
          @expired="expireMfa"
        />
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
      <button v-if="passkeySupported" class="page-button-primary mb-5 w-full" type="button" :disabled="passkeyLoading" @click="submitPasskeyLogin">
        {{ passkeyLoading ? 'Passkey wird geprüft …' : 'Mit Passkey anmelden' }}
      </button>
      <div v-if="passkeySupported" class="mb-5 flex items-center gap-3 text-xs font-semibold uppercase tracking-wider text-slate-400"><span class="h-px flex-1 bg-slate-200" /><span>oder</span><span class="h-px flex-1 bg-slate-200" /></div>
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
import { isPasskeySupported } from '~/utils/webauthn'

definePageMeta({ middleware: 'guest' })
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const email = ref('')
const password = ref('')
const remember = ref(true)
const loading = ref(false)
const error = ref('')
const passkeySupported = ref(false)
const passkeyLoading = ref(false)
const mfaStep = computed(() => Boolean(authStore.mfaChallenge))
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
  passkeySupported.value = isPasskeySupported()
  if (!route.query.auth_error && !route.query.account) return
  const query = { ...route.query }
  delete query.auth_error
  delete query.account
  await router.replace({ query })
})

async function submitPasskeyLogin() {
  passkeyLoading.value = true
  error.value = ''
  try {
    await authStore.loginWithPasskey()
    await router.push(redirectTarget.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Die Passkey-Anmeldung ist fehlgeschlagen.'
  } finally {
    passkeyLoading.value = false
  }
}

async function submit() {
  loading.value = true
  error.value = ''
  authErrorCode.value = ''
  try {
    const result = await authStore.login({ email: email.value, password: password.value, remember: remember.value })
    if (result.status === 'authenticated') await router.push(redirectTarget.value)
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

function expireMfa(message: string) {
  authStore.clearMfaChallenge()
  error.value = message
}

function backToLogin() {
  authStore.clearMfaChallenge()
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
