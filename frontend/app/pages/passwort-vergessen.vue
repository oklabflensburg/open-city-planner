<template>
  <main class="px-4 py-12">
    <AuthCard eyebrow="Sicherheit" title="Passwort vergessen">
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="email" v-model="email" label="E-Mail-Adresse" type="email" autocomplete="email" required :disabled="loading" />
        <p v-if="message" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="min-h-11 rounded-md bg-[#154d73] px-4 text-sm font-bold text-white disabled:opacity-60" type="submit" :disabled="loading">
          Reset-Link senden
        </button>
      </form>
    </AuthCard>
  </main>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'guest' })
const authStore = useAuthStore()
const email = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await authStore.forgotPassword(email.value)
    message.value = 'Wenn ein Konto mit dieser E-Mail-Adresse existiert, wurde eine E-Mail zum Zurücksetzen versendet.'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Anfrage fehlgeschlagen.'
  } finally {
    loading.value = false
  }
}

usePageSeo({
  title: 'Passwort vergessen',
  description: 'Fordere einen Link zum Zurücksetzen deines Passworts an.',
  path: '/passwort-vergessen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
