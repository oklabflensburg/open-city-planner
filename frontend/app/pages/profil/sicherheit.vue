<template>
  <main class="mx-auto max-w-xl px-5 py-12 sm:px-6 lg:px-8">
    <h1 class="text-3xl font-bold text-[#202427]">Sicherheit</h1>
    <section class="mt-8 rounded-lg border border-[#dfe4e6] bg-white p-6">
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="current-password" v-model="currentPassword" label="Aktuelles Passwort" type="password" autocomplete="current-password" required />
        <FormField id="new-password" v-model="newPassword" label="Neues Passwort" type="password" autocomplete="new-password" required />
        <FormField id="new-password-confirm" v-model="newPasswordConfirm" label="Neues Passwort wiederholen" type="password" autocomplete="new-password" required />
        <p v-if="message" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="min-h-11 rounded-md bg-[#154d73] px-4 text-sm font-bold text-white" type="submit">Passwort ändern</button>
      </form>
      <button class="mt-4 min-h-11 rounded-md border border-[#d7dddf] px-4 text-sm font-bold text-[#30363a]" type="button" @click="logoutAll">Auf allen Geräten abmelden</button>
    </section>
  </main>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
const authStore = useAuthStore()
const router = useRouter()
const currentPassword = ref('')
const newPassword = ref('')
const newPasswordConfirm = ref('')
const message = ref('')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    await authStore.changePassword(currentPassword.value, newPassword.value, newPasswordConfirm.value)
    message.value = 'Passwort geändert.'
    currentPassword.value = ''
    newPassword.value = ''
    newPasswordConfirm.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Passwort konnte nicht geändert werden.'
  }
}

async function logoutAll() {
  await authStore.logoutAll()
  await router.push('/login')
}

usePageSeo({
  title: 'Sicherheit',
  description: 'Verwalte Passwort und aktive Sitzungen deines Kontos.',
  path: '/profil/sicherheit',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
