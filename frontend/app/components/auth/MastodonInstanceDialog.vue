<template>
  <AppModal
    :open="open"
    :title="mode === 'link' ? 'Mastodon verbinden' : 'Mit Mastodon anmelden'"
    description="Auf welcher Mastodon-Instanz liegt dein Konto?"
    described-by="mastodon-instance-help mastodon-instance-error"
    :busy="loading"
    size="sm"
    @update:open="emit('update:open', $event)"
  >
    <form class="grid gap-4" @submit.prevent="submit">
      <label for="mastodon-instance" class="block">
        <span class="field-label">Mastodon-Instanz</span>
        <input
          id="mastodon-instance"
          v-model="instance"
          class="field-input"
          name="mastodon-instance"
          type="text"
          inputmode="url"
          autocomplete="url"
          placeholder="norden.social"
          maxlength="255"
          required
          data-autofocus
          aria-describedby="mastodon-instance-help mastodon-instance-error"
          :aria-invalid="Boolean(error)"
          :disabled="loading"
        >
      </label>
      <p id="mastodon-instance-help" class="text-sm leading-6 text-slate-600">
        Beispiel: norden.social, mastodon.social oder @name@norden.social. Deine Zugangsdaten gibst du ausschließlich auf deiner Mastodon-Instanz ein.
      </p>
      <p v-if="error" id="mastodon-instance-error" class="rounded-lg bg-rose-50 p-3 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button class="page-button-secondary" type="button" :disabled="loading" @click="emit('update:open', false)">Abbrechen</button>
        <button class="page-button-primary" type="submit" :disabled="loading || !instance.trim()">{{ loading ? 'Wird vorbereitet …' : 'Weiter' }}</button>
      </div>
    </form>
  </AppModal>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  open: boolean
  mode?: 'login' | 'link'
  defaultInstance?: string | null
  loading?: boolean
  error?: string
}>(), {
  mode: 'login',
  defaultInstance: 'https://norden.social',
  loading: false,
  error: ''
})

const emit = defineEmits<{
  'update:open': [open: boolean]
  submit: [instance: string]
}>()
const instance = ref('')

watch(() => props.open, (open) => {
  if (open) instance.value = props.defaultInstance || 'norden.social'
})

function submit() {
  const value = instance.value.trim()
  if (value) emit('submit', value)
}
</script>
