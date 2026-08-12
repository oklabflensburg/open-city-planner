<template>
  <main class="px-4 py-12">
    <AuthCard eyebrow="Konto" title="Anmelden">
      <p v-if="oauthErrorMessage" class="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ oauthErrorMessage }}</p>
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="email" v-model="email" label="E-Mail" type="email" autocomplete="email" required :disabled="loading" />
        <FormField id="password" v-model="password" label="Passwort" type="password" autocomplete="current-password" required :disabled="loading" />
        <label class="flex items-center gap-2 text-sm text-[#4f575c]">
          <input v-model="remember" class="accent-[#154d73]" type="checkbox">
          Angemeldet bleiben
        </label>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="min-h-11 rounded-md bg-[#154d73] px-4 text-sm font-bold text-white disabled:opacity-60" type="submit" :disabled="loading">
          Anmelden
        </button>
      </form>
      <OAuthLoginButtons class="mt-5" mode="login" :redirect="redirectTarget" />
      <div class="mt-5 grid gap-2 text-sm">
        <NuxtLink class="font-semibold text-[#154d73]" to="/passwort-vergessen">Passwort vergessen?</NuxtLink>
        <NuxtLink class="font-semibold text-[#154d73]" to="/registrieren">Noch kein Konto? Registrieren</NuxtLink>
      </div>
    </AuthCard>
  </main>
</template>

<script setup lang="ts">
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
const redirectTarget = computed(() => sanitizeInternalRedirect(route.query.redirect))
const oauthErrorMessage = computed(() => oauthErrorText(typeof route.query.oauth_error === 'string' ? route.query.oauth_error : ''))

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login({ email: email.value, password: password.value, remember: remember.value })
    await router.push(redirectTarget.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen.'
  } finally {
    loading.value = false
  }
}

function oauthErrorText(code: string) {
  return {
    OAUTH_ACCESS_DENIED: 'Die Anmeldung wurde abgebrochen.',
    OAUTH_EMAIL_CONFLICT: 'Zu dieser E-Mail-Adresse existiert bereits ein Konto. Melde dich zuerst mit deinem Passwort an und verknüpfe den Anbieter anschließend im Profil.',
    OAUTH_ACCOUNT_ALREADY_LINKED: 'Dieses externe Konto ist bereits mit einem anderen Benutzerkonto verbunden.',
    OAUTH_PROVIDER_NOT_SUPPORTED: 'Dieser Anmeldeanbieter wird nicht unterstützt.',
    OAUTH_PROVIDER_DISABLED: 'Dieser Anmeldeanbieter ist aktuell nicht aktiviert.',
    INVALID_OAUTH_STATE: 'Die OAuth-Anmeldung ist abgelaufen. Bitte versuche es erneut.',
    OAUTH_LOGIN_FAILED: 'Die externe Anmeldung konnte nicht abgeschlossen werden.',
    AUTH_REQUIRED: 'Bitte melde dich zuerst an.'
  }[code] || ''
}

usePageSeo({
  title: 'Anmelden',
  description: 'Melde dich bei der Open City Map an.',
  path: '/login',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
