<template>
  <AuthPageShell label="Registrieren">
    <AuthCard eyebrow="Konto" title="Konto erstellen">
      <form class="grid gap-4" @submit.prevent="submit">
        <div class="grid min-w-0 gap-4 md:grid-cols-2">
          <FormField id="first-name" v-model="firstName" label="Vorname" autocomplete="given-name" :disabled="loading" />
          <FormField id="last-name" v-model="lastName" label="Nachname" autocomplete="family-name" :disabled="loading" />
        </div>
        <FormField id="email" v-model="email" label="E-Mail" type="email" autocomplete="email" required :disabled="loading" />
        <FormField id="password" v-model="password" label="Passwort" type="password" autocomplete="new-password" required :disabled="loading" />
        <FormField id="password-confirm" v-model="passwordConfirm" label="Passwort bestätigen" type="password" autocomplete="new-password" required :disabled="loading" />
        <label class="flex items-start gap-2 text-sm text-[#4f575c]">
          <input v-model="privacyRead" class="mt-1 accent-[#154d73]" type="checkbox" required>
          <span>Ich habe die <NuxtLink class="font-semibold text-[#154d73]" to="/datenschutz">Datenschutzerklärung</NuxtLink> gelesen.</span>
        </label>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <p v-if="success" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ success }}</p>
        <button class="page-button-primary disabled:opacity-60" type="submit" :disabled="loading">
          Registrieren
        </button>
      </form>
      <OAuthLoginButtons class="mt-5" mode="signup" redirect="/" />
      <NuxtLink class="mt-5 block text-sm font-semibold text-[#154d73]" to="/login">Bereits registriert? Anmelden</NuxtLink>
    </AuthCard>
  </AuthPageShell>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'guest' })
const router = useRouter()
const authStore = useAuthStore()
const firstName = ref('')
const lastName = ref('')
const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const privacyRead = ref(false)
const loading = ref(false)
const error = ref('')
const success = ref('')

async function submit() {
  error.value = ''
  success.value = ''
  if (password.value !== passwordConfirm.value) {
    error.value = 'Die Passwörter stimmen nicht überein.'
    return
  }
  loading.value = true
  try {
    await authStore.signup({ email: email.value, password: password.value, first_name: firstName.value, last_name: lastName.value })
    success.value = 'Registrierung erfolgreich. Bitte bestätige deine E-Mail-Adresse, bevor du Flächen bearbeitest.'
    window.setTimeout(() => void router.push('/'), 1200)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Registrierung fehlgeschlagen.'
  } finally {
    loading.value = false
  }
}

usePageSeo({
  title: 'Registrieren',
  description: 'Erstelle ein Konto für die Open City Map.',
  path: '/registrieren',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
