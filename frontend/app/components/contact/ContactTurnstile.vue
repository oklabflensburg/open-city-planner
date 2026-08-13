<template>
  <div>
    <div ref="container" />
    <p v-if="error" class="mt-2 text-sm font-semibold text-rose-700" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string
  remove: (widgetId: string) => void
}

const props = defineProps<{ siteKey: string }>()
const emit = defineEmits<{ 'update:token': [token: string] }>()
const container = ref<HTMLElement | null>(null)
const error = ref('')
let widgetId = ''

function turnstileApi() {
  return (window as typeof window & { turnstile?: TurnstileApi }).turnstile
}

async function loadScript() {
  const existing = document.querySelector<HTMLScriptElement>('script[data-Stadtplaner-turnstile]')
  if (existing) {
    if (turnstileApi()) return
    await new Promise<void>((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('Turnstile konnte nicht geladen werden.')), { once: true })
    })
    return
  }
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.defer = true
    script.dataset.StadtplanerTurnstile = 'true'
    script.addEventListener('load', () => resolve(), { once: true })
    script.addEventListener('error', () => reject(new Error('Turnstile konnte nicht geladen werden.')), { once: true })
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    await loadScript()
    const api = turnstileApi()
    if (!api || !container.value) throw new Error('Turnstile ist nicht verfügbar.')
    widgetId = api.render(container.value, {
      sitekey: props.siteKey,
      callback: (token: string) => emit('update:token', token),
      'expired-callback': () => emit('update:token', ''),
      'error-callback': () => {
        emit('update:token', '')
        error.value = 'Die Sicherheitsprüfung konnte nicht geladen werden.'
      }
    })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Die Sicherheitsprüfung konnte nicht geladen werden.'
  }
})

onBeforeUnmount(() => {
  if (widgetId) turnstileApi()?.remove(widgetId)
})
</script>
