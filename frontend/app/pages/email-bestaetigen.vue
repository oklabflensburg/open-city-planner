<template>
  <AuthPageShell label="E-Mail bestätigen">
    <AuthCard eyebrow="Konto" :title="title">
      <p class="text-sm leading-6 text-[#4f575c]">{{ message }}</p>
      <div class="mt-5 flex flex-wrap gap-2">
        <NuxtLink class="page-button-primary" to="/">Zur Karte</NuxtLink>
        <NuxtLink v-if="!authStore.authenticated" class="page-button-secondary" to="/login">
          Anmelden
        </NuxtLink>
        <button v-if="failed && needsEmailVerification(authStore.user)" class="page-button-secondary" type="button" @click="authStore.resendVerification()">
          Neue Bestätigungs-E-Mail anfordern
        </button>
      </div>
    </AuthCard>
  </AuthPageShell>
</template>

<script setup lang="ts">
const route = useRoute()
const authStore = useAuthStore()
const title = ref('E-Mail-Adresse bestätigen')
const message = ref('E-Mail-Adresse wird bestätigt …')
const failed = ref(false)

onMounted(async () => {
  try {
    const result = await authStore.verifyEmail(String(route.query.token || ''))
    const copy = verificationPageCopy(result.status)
    title.value = copy.title
    message.value = copy.message
  } catch {
    failed.value = true
    message.value = 'Der Bestätigungslink ist ungültig oder abgelaufen.'
  }
})

usePageSeo({
  title: 'E-Mail bestätigen',
  description: 'E-Mail-Adresse des Kontos bestätigen.',
  path: '/email-bestaetigen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
