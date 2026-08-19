<template>
  <AuthPageShell label="Zwei-Faktor-Authentifizierung">
    <AuthCard eyebrow="Konto" title="Anmeldung bestätigen">
      <MfaChallengeForm
        v-if="ready"
        :redirect-target="redirectTarget"
        replace-navigation
        @back="backToLogin"
        @expired="expireMfa"
      />
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
const error = ref('')
const ready = ref(false)
const redirectTarget = sanitizeInternalRedirect(route.query.redirect)

onMounted(async () => {
  try {
    // Die HttpOnly-Cookie-Challenge bleibt geheim; ihre Methoden kommen direkt vom Backend.
    await authStore.loadMfaChallenge()
    ready.value = true
    await router.replace({ path: '/auth/mfa' })
  } catch (cause) {
    error.value = cause instanceof Error
      ? cause.message
      : 'Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.'
  }
})

function expireMfa(message: string) {
  authStore.clearMfaChallenge()
  ready.value = false
  error.value = message
}

async function backToLogin() {
  authStore.clearMfaChallenge()
  await router.replace('/login')
}

usePageSeo({
  title: 'Zwei-Faktor-Authentifizierung',
  description: 'Anmeldung bestätigen.',
  path: '/auth/mfa',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
