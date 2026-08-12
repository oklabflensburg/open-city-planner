<template>
  <main class="px-4 py-12">
    <AuthCard eyebrow="Konto" title="Anmeldung wird abgeschlossen">
      <p class="text-sm leading-6 text-[#4f575c]" aria-live="polite">
        Deine Sitzung wird geprüft.
      </p>
      <p v-if="error" class="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>
    </AuthCard>
  </main>
</template>

<script setup lang="ts">
import { sanitizeInternalRedirect } from '~/utils/redirect'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const error = ref('')

onMounted(async () => {
  try {
    const redirect = await authStore.handleOAuthCallback(sanitizeInternalRedirect(route.query.redirect))
    await router.replace(redirect)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Die Anmeldung konnte nicht abgeschlossen werden.'
    window.setTimeout(() => {
      void router.replace({ path: '/login', query: { oauth_error: 'OAUTH_LOGIN_FAILED' } })
    }, 900)
  }
})

usePageSeo({
  title: 'Anmeldung wird abgeschlossen',
  description: 'Die externe Anmeldung wird abgeschlossen.',
  path: '/auth/callback',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
