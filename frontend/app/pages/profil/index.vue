<template>
  <ContentPageShell title="Profil" description="Persönliche Angaben, Profilbild und verbundene Konten verwalten." eyebrow="Konto" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Profil' }]" max-width="reading">
    <div class="space-y-6 sm:space-y-8">
    <Card v-if="needsOAuthEmail" class="border-amber-200 bg-amber-50 p-5 sm:p-7">
      <h2 class="text-lg font-bold text-slate-950">Fast geschafft</h2>
      <p class="mt-2 text-sm leading-6 text-slate-700">Bitte hinterlege eine E-Mail-Adresse für dein Stadtplaner-Konto. Wir senden dir anschließend einen Bestätigungslink.</p>
      <form class="mt-5 grid gap-4" @submit.prevent="completeEmail">
        <FormField id="oauth-email" v-model="oauthEmail" label="E-Mail-Adresse" type="email" autocomplete="email" required :disabled="emailLoading" />
        <p v-if="emailError" class="rounded-md bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800" role="alert">{{ emailError }}</p>
        <p v-if="emailMessage" class="rounded-md bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800" role="status">{{ emailMessage }}</p>
        <button class="page-button-primary" type="submit" :disabled="emailLoading">{{ emailLoading ? 'Wird gespeichert …' : 'E-Mail hinterlegen' }}</button>
      </form>
    </Card>
    <AvatarUploader />
    <OAuthAccountList />
    <Card class="p-5 sm:p-7">
      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt class="font-semibold text-[#687176]">E-Mail</dt><dd>{{ needsOAuthEmail ? 'Noch nicht hinterlegt' : authStore.user?.email }}</dd></div>
        <div><dt class="font-semibold text-[#687176]">E-Mail bestätigt</dt><dd>{{ authStore.user?.is_verified ? 'Ja' : 'Nein' }}</dd></div>
        <div><dt class="font-semibold text-[#687176]">Registriert seit</dt><dd>{{ formatDate(authStore.user?.created_at) }}</dd></div>
        <div><dt class="font-semibold text-[#687176]">Letzter Login</dt><dd>{{ formatDate(authStore.user?.last_login_at) }}</dd></div>
      </dl>
      <form class="mt-6 grid gap-4" @submit.prevent="submit">
        <FormField id="first-name" v-model="firstName" label="Vorname" autocomplete="given-name" />
        <FormField id="last-name" v-model="lastName" label="Nachname" autocomplete="family-name" />
        <FormField id="display-name" v-model="displayName" label="Anzeigename" autocomplete="name" />
        <p v-if="message" class="rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
        <button class="page-button-primary" type="submit">Profil speichern</button>
      </form>
    </Card>
    <AccountDangerZone />
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
const authStore = useAuthStore()
const firstName = ref(authStore.user?.first_name || '')
const lastName = ref(authStore.user?.last_name || '')
const displayName = ref(authStore.user?.display_name || '')
const message = ref('')
const oauthEmail = ref('')
const emailLoading = ref(false)
const emailError = ref('')
const emailMessage = ref('')
const needsOAuthEmail = computed(() => Boolean(authStore.user?.email_pending))

async function submit() {
  await authStore.updateProfile({ first_name: firstName.value, last_name: lastName.value, display_name: displayName.value })
  message.value = 'Profil gespeichert.'
}

async function completeEmail() {
  emailLoading.value = true
  emailError.value = ''
  try {
    const result = await authStore.completeOAuthEmail(oauthEmail.value)
    emailMessage.value = result.message
  } catch (error) {
    emailError.value = error instanceof Error ? error.message : 'Die E-Mail-Adresse konnte nicht gespeichert werden.'
  } finally {
    emailLoading.value = false
  }
}

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE').format(new Date(value)) : 'Noch nicht vorhanden'
}

usePageSeo({
  title: 'Profil',
  description: 'Verwalte dein persönliches Profil.',
  path: '/profil',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
