<template>
  <ContentPageShell title="Sicherheit" description="Passwort und aktive Anmeldungen Ihres Kontos verwalten." eyebrow="Konto" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Profil', to: '/profil' }, { label: 'Sicherheit' }]" max-width="reading">
    <Card class="p-5 sm:p-7">
      <form class="grid gap-4" @submit.prevent="submit">
        <FormField id="current-password" v-model="currentPassword" label="Aktuelles Passwort" type="password" autocomplete="current-password" required />
        <FormField id="new-password" v-model="newPassword" label="Neues Passwort" type="password" autocomplete="new-password" required />
        <FormField id="new-password-confirm" v-model="newPasswordConfirm" label="Neues Passwort wiederholen" type="password" autocomplete="new-password" required />
        <p v-if="message" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{{ error }}</p>
        <button class="page-button-primary" type="submit">Passwort ändern</button>
      </form>
      <button class="page-button-secondary mt-4" type="button" @click="logoutAll">Auf allen Geräten abmelden</button>
    </Card>
  </ContentPageShell>
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
