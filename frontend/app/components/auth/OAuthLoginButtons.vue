<template>
  <div v-if="hasOAuthProviders(authStore.oauthProviders)" class="grid gap-3">
    <AuthDivider label="oder fortfahren mit" />
    <div class="grid gap-2" aria-live="polite">
      <button
        v-for="provider in authStore.oauthProviders"
        :key="provider.id"
        class="grid min-h-11 w-full grid-cols-[1.5rem_minmax(0,1fr)_1.5rem] items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-wait disabled:opacity-70"
        type="button"
        :aria-label="`${buttonLabel(provider.label)}`"
        :disabled="loadingProvider !== ''"
        @click="start(provider.id)"
      >
        <ProviderIcon :provider="provider.id" class="size-5 justify-self-center text-slate-950" />
        <span class="min-w-0 text-center [overflow-wrap:anywhere]">{{ loadingProvider === provider.id ? `Verbindung zu ${provider.label} wird hergestellt …` : buttonLabel(provider.label) }}</span>
        <span aria-hidden="true" />
      </button>
    </div>
    <MastodonInstanceDialog
      :open="mastodonDialogOpen"
      mode="login"
      :default-instance="mastodonProvider?.default_instance"
      :loading="loadingProvider === 'mastodon'"
      :error="mastodonError"
      @update:open="mastodonDialogOpen = $event"
      @submit="startMastodon"
    />
  </div>
</template>

<script setup lang="ts">
import type { OAuthMode } from '~/utils/oauth'
import { hasOAuthProviders, oauthButtonLabel } from '~/utils/oauth'

const props = withDefaults(defineProps<{
  mode?: OAuthMode
  redirect?: string
}>(), {
  mode: 'login',
  redirect: '/'
})

const authStore = useAuthStore()
const loadingProvider = ref('')
const mastodonDialogOpen = ref(false)
const mastodonError = ref('')
const mastodonProvider = computed(() => authStore.oauthProviders.find(provider => provider.id === 'mastodon'))

onMounted(() => {
  void authStore.loadProviders()
})

function start(providerId: string) {
  const provider = authStore.oauthProviders.find(item => item.id === providerId)
  if (provider?.requires_instance) {
    mastodonError.value = ''
    mastodonDialogOpen.value = true
    return
  }
  loadingProvider.value = providerId
  void authStore.startOAuthLogin(providerId, props.redirect)
}

async function startMastodon(instance: string) {
  loadingProvider.value = 'mastodon'
  mastodonError.value = ''
  try {
    await authStore.startOAuthLogin('mastodon', props.redirect, instance)
  } catch (error) {
    loadingProvider.value = ''
    mastodonError.value = error instanceof Error ? error.message : 'Die Mastodon-Anmeldung konnte nicht vorbereitet werden.'
  }
}

function buttonLabel(label: string) {
  return oauthButtonLabel(label, props.mode)
}
</script>
