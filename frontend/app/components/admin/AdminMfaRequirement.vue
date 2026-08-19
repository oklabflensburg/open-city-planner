<template>
  <div v-if="requirement && route.path.startsWith('/admin/')" class="mx-auto mt-5 max-w-7xl px-4 sm:px-6 lg:px-8" role="alert">
    <div class="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
      <p class="font-bold">{{ title }}</p>
      <p class="mt-1">{{ message }}</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <NuxtLink to="/profil/sicherheit" class="font-bold underline underline-offset-2">MFA-Sicherheit verwalten</NuxtLink>
        <button v-if="requirement === 'MFA_REAUTH_REQUIRED'" type="button" class="font-bold underline underline-offset-2" @click="signInAgain">Mit MFA neu anmelden</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const authStore = useAuthStore()
const requirement = useState<'MFA_SETUP_REQUIRED' | 'MFA_REAUTH_REQUIRED' | null>('admin-mfa-requirement', () => null)
const title = computed(() => requirement.value === 'MFA_SETUP_REQUIRED' ? 'MFA-Einrichtung erforderlich' : 'Erneute MFA-Anmeldung erforderlich')
const message = computed(() => requirement.value === 'MFA_SETUP_REQUIRED'
  ? 'Administrative Funktionen werden erst nach Einrichtung einer starken Anmeldemethode freigeschaltet.'
  : 'Ihre aktuelle Sitzung enthält keine bestätigte Zwei-Faktor-Anmeldung.')

async function signInAgain() {
  const redirect = route.fullPath
  try { await authStore.logout() } finally {
    requirement.value = null
    await navigateTo(`/login?redirect=${encodeURIComponent(redirect)}`)
  }
}
</script>
