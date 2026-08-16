<template>
  <div v-if="hasOAuthProviders(authStore.oauthProviders)" class="grid gap-3">
    <AuthDivider :label="mode === 'signup' ? 'oder registrieren mit' : 'oder anmelden mit'" />
    <div class="grid gap-2" aria-live="polite">
      <button
        v-for="provider in authStore.oauthProviders"
        :key="provider.id"
        class="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-wait disabled:opacity-70"
        type="button"
        :aria-label="`${buttonLabel(provider.label)}`"
        :disabled="loadingProvider !== ''"
        @click="start(provider.id)"
      >
        <Github v-if="provider.id === 'github'" class="mr-2 size-4" aria-hidden="true" />
        <MessageCircle v-else-if="provider.id === 'mastodon'" class="mr-2 size-4" aria-hidden="true" />
        {{ loadingProvider === provider.id ? `Zu ${provider.label} weiterleiten ...` : buttonLabel(provider.label) }}
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
import { Github, MessageCircle } from 'lucide-vue-next'
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
