<template>
  <section class="rounded-lg border border-[#dfe4e6] bg-white p-6">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 class="text-lg font-bold text-[#202427]">Verknüpfte Konten</h2>
        <p class="mt-1 text-sm leading-6 text-[#687176]">Verbinde externe Anmeldungen mit deinem lokalen Konto.</p>
      </div>
    </div>

    <div v-if="authStore.oauthProviders.length" class="mt-5 grid gap-3">
      <div v-for="provider in authStore.oauthProviders" :key="provider.id" class="flex flex-col gap-3 rounded-lg border border-[#edf0f1] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="font-bold text-[#202427]">{{ provider.label }}</p>
          <p class="mt-1 text-sm text-[#687176]">
            {{ accountFor(provider.id)?.provider_username || accountFor(provider.id)?.provider_email || 'Nicht verbunden' }}
          </p>
          <p v-if="accountFor(provider.id)?.last_login_at" class="mt-1 text-xs text-[#8b9499]">
            Zuletzt genutzt: {{ formatDate(accountFor(provider.id)?.last_login_at) }}
          </p>
        </div>
        <button
          v-if="accountFor(provider.id)"
          class="min-h-11 rounded-md border border-[#cfd8dc] px-4 text-sm font-bold text-[#30363a] transition hover:bg-[#f4f6f6] disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          :disabled="loadingProvider === provider.id"
          @click="unlink(provider.id, provider.label)"
        >
          {{ loadingProvider === provider.id ? 'Löst ...' : 'Verknüpfung lösen' }}
        </button>
        <button
          v-else
          class="inline-flex min-h-11 items-center justify-center rounded-md bg-[#154d73] px-4 text-sm font-bold text-white transition hover:bg-[#0f3f61] disabled:cursor-wait disabled:opacity-60"
          type="button"
          :disabled="loadingProvider === provider.id"
          @click="link(provider.id)"
        >
          {{ loadingProvider === provider.id ? `Weiterleitung zu ${provider.label} …` : `${provider.label} verbinden` }}
        </button>
      </div>
    </div>
    <p v-else class="mt-5 rounded-md bg-[#f4f7f8] px-3 py-2 text-sm text-[#687176]">Es sind aktuell keine externen Anmeldeanbieter konfiguriert.</p>

    <p v-if="message" class="mt-4 rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
    <p v-if="error" class="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loadingProvider = ref('')
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    await Promise.all([authStore.loadProviders(), authStore.loadOAuthAccounts()])
    applyCallbackFeedback()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Verknüpfte Konten konnten nicht geladen werden.'
  }
})

function accountFor(provider: string) {
  return authStore.oauthAccounts.find((account) => account.provider === provider)
}

function link(provider: string) {
  loadingProvider.value = provider
  message.value = ''
  error.value = ''
  authStore.startOAuthLink(provider)
}

async function unlink(provider: string, label: string) {
  loadingProvider.value = provider
  message.value = ''
  error.value = ''
  try {
    await authStore.unlinkOAuthAccount(provider)
    message.value = `${label} wurde getrennt.`
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Die Verknüpfung konnte nicht entfernt werden.'
  } finally {
    loadingProvider.value = ''
  }
}

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE').format(new Date(value)) : ''
}

function applyCallbackFeedback() {
  const provider = typeof route.query.provider === 'string' ? route.query.provider : ''
  const label = authStore.oauthProviders.find(item => item.id === provider)?.label || providerLabel(provider)
  const success = typeof route.query.oauth_link === 'string' ? route.query.oauth_link : ''
  const errorCode = typeof route.query.oauth_link_error === 'string' ? route.query.oauth_link_error : ''

  if (success === 'success' && label) {
    message.value = `${label} wurde erfolgreich mit deinem Konto verknüpft.`
  } else if (success === 'already_connected' && label) {
    message.value = `${label} ist bereits mit deinem Konto verknüpft.`
  } else if (errorCode) {
    error.value = oauthLinkErrorText(errorCode, label)
  } else {
    return
  }

  const { oauth_link: _success, oauth_link_error: _error, provider: _provider, ...query } = route.query
  void router.replace({ query })
}

function providerLabel(provider: string) {
  return { github: 'GitHub', google: 'Google' }[provider] || ''
}

function oauthLinkErrorText(code: string, provider: string) {
  return {
    OAUTH_ACCOUNT_ALREADY_LINKED: `Dieses ${provider || 'externe'}-Konto ist bereits mit einem anderen Benutzerkonto verbunden.`,
    OAUTH_ACCESS_DENIED: 'Die Verknüpfung wurde abgebrochen.',
    INVALID_OAUTH_STATE: 'Die Verknüpfung ist abgelaufen. Bitte versuche es erneut.',
    AUTH_REQUIRED: 'Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.',
    OAUTH_PROVIDER_DISABLED: 'Dieser Anbieter ist aktuell nicht aktiviert.',
    OAUTH_LINK_FAILED: 'Die Verknüpfung konnte nicht abgeschlossen werden.'
  }[code] || 'Die Verknüpfung konnte nicht abgeschlossen werden.'
}
</script>
