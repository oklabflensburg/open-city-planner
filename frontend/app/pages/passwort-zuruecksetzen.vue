<template>
  <AuthPageShell label="Passwort zurücksetzen">
    <AuthCard eyebrow="Sicherheit" title="Passwort zurücksetzen">
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="password" v-model="password" label="Neues Passwort" type="password" autocomplete="new-password" required :disabled="loading" />
        <FormField id="password-confirm" v-model="passwordConfirm" label="Neues Passwort wiederholen" type="password" autocomplete="new-password" required :disabled="loading" />
        <p v-if="message" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="page-button-primary disabled:opacity-60" type="submit" :disabled="loading">
          Passwort speichern
        </button>
      </form>
    </AuthCard>
  </AuthPageShell>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const password = ref('')
const passwordConfirm = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')

async function submit() {
  const token = String(route.query.token || '')
  if (!token) {
    error.value = 'Der Reset-Link ist ungültig.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await authStore.resetPassword(token, password.value, passwordConfirm.value)
    message.value = 'Passwort wurde zurückgesetzt.'
    window.setTimeout(() => void router.push('/login'), 1200)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Passwort konnte nicht zurückgesetzt werden.'
  } finally {
    loading.value = false
  }
}

usePageSeo({
  title: 'Passwort zurücksetzen',
  description: 'Neues Passwort für das Konto festlegen.',
  path: '/passwort-zuruecksetzen',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
