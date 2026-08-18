<template>
  <section class="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-7">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 class="text-lg font-bold text-[#202427]">Verknüpfte Konten</h2>
        <p class="mt-1 text-sm leading-6 text-[#687176]">Externe Anmeldungen mit dem lokalen Konto verbinden.</p>
      </div>
    </div>

    <div v-if="authStore.oauthProviders.length" class="mt-5 grid gap-3">
      <div v-for="provider in authStore.oauthProviders" :key="provider.id" class="flex flex-col gap-3 rounded-lg border border-[#edf0f1] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="min-w-0">
          <p class="flex items-center gap-2 font-bold text-[#202427]"><ProviderIcon :provider="provider.id" class="size-5 text-slate-950" /> {{ provider.label }}</p>
          <p class="mt-1 text-sm text-[#687176]">
            {{ accountFor(provider.id)?.provider_username || accountFor(provider.id)?.provider_email || 'Nicht verbunden' }}
          </p>
          <p v-if="accountFor(provider.id)?.last_login_at" class="mt-1 text-xs text-[#8b9499]">
            Zuletzt genutzt: {{ formatDate(accountFor(provider.id)?.last_login_at) }}
          </p>
          <a v-if="accountFor(provider.id)?.provider_profile_url" :href="accountFor(provider.id)?.provider_profile_url || undefined" target="_blank" rel="noopener noreferrer" class="mt-1 inline-block break-all text-sm font-semibold text-[#154d73] underline">Mastodon-Profil öffnen</a>
        </div>
        <button
          v-if="accountFor(provider.id)"
          class="page-button-secondary disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          :disabled="loadingProvider === provider.id"
          @click="requestUnlink(provider.id, provider.label)"
        >
          <ProviderIcon :provider="provider.id" class="size-4 text-slate-950" />
          {{ loadingProvider === provider.id ? 'Wird getrennt …' : 'Verknüpfung lösen' }}
        </button>
        <button
          v-else
          class="page-button-primary disabled:cursor-wait disabled:opacity-60"
          type="button"
          :disabled="loadingProvider === provider.id"
          @click="link(provider.id)"
        >
          <ProviderIcon :provider="provider.id" class="size-4 text-slate-950" />
          {{ loadingProvider === provider.id ? `Verbindung zu ${provider.label} wird hergestellt …` : `${provider.label}-Konto verknüpfen` }}
        </button>
      </div>
    </div>
    <p v-else class="mt-5 rounded-md bg-[#f4f7f8] px-3 py-2 text-sm text-[#687176]">Es sind aktuell keine externen Anmeldeanbieter konfiguriert.</p>

    <p v-if="message" class="mt-4 rounded-md bg-[#edf4f8] px-3 py-2 text-sm font-semibold text-[#154d73]">{{ message }}</p>
    <p v-if="error" class="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert">{{ error }}</p>

    <AppConfirmDialog
      :open="Boolean(pendingUnlink)"
      title="Verknüpfung lösen?"
      :body="`${pendingUnlink?.label || 'Das externe Konto'} wird von Ihrem Stadtplaner-Konto getrennt. Prüfen Sie vorher, ob weiterhin eine Anmeldung möglich ist.`"
      confirm-label="Verknüpfung lösen"
      loading-label="Wird getrennt …"
      variant="warning"
      :loading="Boolean(pendingUnlink && loadingProvider === pendingUnlink.provider)"
      :error="unlinkError"
      @update:open="handleConfirmOpen"
      @confirm="confirmUnlink"
    />
    <MastodonInstanceDialog
      :open="mastodonDialogOpen"
      mode="link"
      :default-instance="mastodonProvider?.default_instance"
      :loading="loadingProvider === 'mastodon'"
      :error="mastodonError"
      @update:open="mastodonDialogOpen = $event"
      @submit="linkMastodon"
    />
  </section>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loadingProvider = ref('')
const message = ref('')
const error = ref('')
const unlinkError = ref('')
const pendingUnlink = ref<{ provider: string, label: string } | null>(null)
const mastodonDialogOpen = ref(false)
const mastodonError = ref('')
const mastodonProvider = computed(() => authStore.oauthProviders.find(provider => provider.id === 'mastodon'))

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

async function link(provider: string) {
  const definition = authStore.oauthProviders.find(item => item.id === provider)
  if (definition?.requires_instance) {
    mastodonError.value = ''
    mastodonDialogOpen.value = true
    return
  }
  loadingProvider.value = provider
  message.value = ''
  error.value = ''
  try {
    await authStore.startOAuthLink(provider)
  } catch (err) {
    loadingProvider.value = ''
    error.value = err instanceof Error ? err.message : 'Die Verknüpfung konnte nicht gestartet werden.'
  }
}

async function linkMastodon(instance: string) {
  loadingProvider.value = 'mastodon'
  mastodonError.value = ''
  try {
    await authStore.startOAuthLink('mastodon', instance)
  } catch (err) {
    loadingProvider.value = ''
    mastodonError.value = err instanceof Error ? err.message : 'Die Mastodon-Verknüpfung konnte nicht vorbereitet werden.'
  }
}

function requestUnlink(provider: string, label: string) {
  unlinkError.value = ''
  pendingUnlink.value = { provider, label }
}

async function confirmUnlink() {
  if (!pendingUnlink.value || loadingProvider.value) return
  const { provider, label } = pendingUnlink.value
  loadingProvider.value = provider
  message.value = ''
  unlinkError.value = ''
  try {
    await authStore.unlinkOAuthAccount(provider)
    message.value = `${label} wurde getrennt.`
    pendingUnlink.value = null
  } catch (err) {
    unlinkError.value = err instanceof Error ? err.message : 'Die Verknüpfung konnte nicht entfernt werden.'
  } finally {
    loadingProvider.value = ''
  }
}

function handleConfirmOpen(open: boolean) {
  if (open || loadingProvider.value) return
  pendingUnlink.value = null
  unlinkError.value = ''
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
    message.value = `${label} wurde erfolgreich mit Ihrem Konto verknüpft.`
  } else if (success === 'already_connected' && label) {
    message.value = `${label} ist bereits mit Ihrem Konto verknüpft.`
  } else if (errorCode) {
    error.value = oauthLinkErrorText(errorCode, label)
  } else {
    return
  }

  const { oauth_link: _success, oauth_link_error: _error, provider: _provider, ...query } = route.query
  void router.replace({ query })
}

function providerLabel(provider: string) {
  return { github: 'GitHub', google: 'Google', mastodon: 'Mastodon' }[provider] || ''
}

function oauthLinkErrorText(code: string, provider: string) {
  return {
    OAUTH_ACCOUNT_ALREADY_LINKED: `Dieses ${provider || 'externe'}-Konto ist bereits mit einem anderen Benutzerkonto verbunden.`,
    OAUTH_ACCESS_DENIED: 'Die Verknüpfung wurde abgebrochen.',
    INVALID_OAUTH_STATE: 'Die Verknüpfung ist abgelaufen. Bitte versuchen Sie es erneut.',
    AUTH_REQUIRED: 'Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.',
    OAUTH_PROVIDER_DISABLED: 'Dieser Anbieter ist aktuell nicht aktiviert.',
    MASTODON_INSTANCE_UNREACHABLE: 'Die Mastodon-Instanz ist derzeit nicht erreichbar.',
    MASTODON_INSTANCE_UNSUPPORTED: 'Diese Instanz unterstützt die benötigte Mastodon-Anmeldung nicht.',
    OAUTH_LINK_FAILED: 'Die Verknüpfung konnte nicht abgeschlossen werden.'
  }[code] || 'Die Verknüpfung konnte nicht abgeschlossen werden.'
}
</script>
