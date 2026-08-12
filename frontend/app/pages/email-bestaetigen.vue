<template>
  <main class="px-4 py-12">
    <AuthCard eyebrow="Konto" :title="title">
      <p class="text-sm leading-6 text-[#4f575c]">{{ message }}</p>
      <div class="mt-5 flex flex-wrap gap-2">
        <NuxtLink class="rounded-md bg-[#154d73] px-4 py-3 text-sm font-bold text-white" to="/">Zur Karte</NuxtLink>
        <NuxtLink v-if="!authStore.authenticated" class="rounded-md border border-[#d7dddf] px-4 py-3 text-sm font-bold text-[#30363a]" to="/login">
          Anmelden
        </NuxtLink>
        <button v-if="failed && needsEmailVerification(authStore.user)" class="rounded-md border border-[#d7dddf] px-4 py-3 text-sm font-bold text-[#30363a]" type="button" @click="authStore.resendVerification()">
          Neue Bestätigungs-E-Mail anfordern
        </button>
      </div>
    </AuthCard>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const authStore = useAuthStore()
const title = ref('E-Mail-Adresse bestätigen')
const message = ref('Lade...')
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
  description: 'Bestätige die E-Mail-Adresse deines Kontos.',
  path: '/email-bestaetigen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
