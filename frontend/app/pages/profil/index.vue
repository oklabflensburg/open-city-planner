<template>
  <ContentPageShell title="Profil" description="Persönliche Angaben, Profilbild und verbundene Konten verwalten." eyebrow="Konto" :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Profil' }]" max-width="reading">
    <div class="space-y-6 sm:space-y-8">
    <AvatarUploader />
    <OAuthAccountList />
    <Card class="p-5 sm:p-7">
      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt class="font-semibold text-[#687176]">E-Mail</dt><dd>{{ authStore.user?.email }}</dd></div>
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

async function submit() {
  await authStore.updateProfile({ first_name: firstName.value, last_name: lastName.value, display_name: displayName.value })
  message.value = 'Profil gespeichert.'
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
