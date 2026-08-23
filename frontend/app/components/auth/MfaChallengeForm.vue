<template>
  <div class="grid min-w-0 gap-5" data-mfa-challenge>
    <p class="text-sm leading-6 text-slate-600">
      Wählen Sie eine Ihrer eingerichteten Sicherheitsmethoden.
    </p>

    <section v-if="activeMethod === 'passkey'" aria-labelledby="mfa-passkey-title">
      <h2 id="mfa-passkey-title" class="mb-2 font-bold text-slate-950">Passkey</h2>
      <p class="mb-4 text-sm leading-6 text-slate-600">Bestätigen Sie die Anmeldung mit Ihrem Gerät oder Sicherheitsschlüssel.</p>
      <button class="page-button-primary w-full" type="button" :disabled="busy" @click="submitPasskey">
        {{ passkeyLoading ? 'Passkey wird geprüft …' : passkeyNotice ? 'Passkey erneut versuchen' : 'Passkey verwenden' }}
      </button>
      <div v-if="passkeyNotice" class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3" role="status" aria-live="polite">
        <p class="font-semibold text-amber-950">Passkey-Anmeldung nicht abgeschlossen</p>
        <p class="mt-1 text-sm leading-6 text-amber-900">{{ passkeyNotice }} Sie können es erneut versuchen oder eine andere Sicherheitsmethode verwenden.</p>
      </div>
    </section>

    <form v-else-if="activeMethod === 'totp'" class="grid gap-4" @submit.prevent="submitCode">
      <div>
        <h2 class="font-bold text-slate-950">Authenticator-App</h2>
        <p class="mt-1 text-sm leading-6 text-slate-600">Geben Sie den sechsstelligen Code aus Ihrer Authenticator-App ein.</p>
      </div>
      <OtpInput ref="otpInput" v-model="code" :disabled="busy" :invalid="Boolean(error)" described-by="mfa-error" />
      <button class="page-button-primary" type="submit" :disabled="busy || code.length !== 6">
        {{ loading ? 'Code wird geprüft …' : 'Code bestätigen' }}
      </button>
    </form>

    <form v-else-if="activeMethod === 'recovery_code'" class="grid gap-4" @submit.prevent="submitCode">
      <div>
        <h2 class="font-bold text-slate-950">Wiederherstellungscode</h2>
        <p class="mt-1 text-sm leading-6 text-slate-600">Jeder Wiederherstellungscode kann nur einmal verwendet werden.</p>
      </div>
      <FormField
        id="mfa-recovery-code"
        v-model="recoveryCode"
        label="Zwölfstelliger Wiederherstellungscode"
        autocomplete="one-time-code"
        required
        :disabled="busy"
      />
      <p class="-mt-2 text-xs text-slate-500">Zum Beispiel ABCD-EFGH-JKLM. Bindestriche und Leerzeichen sind optional.</p>
      <button class="page-button-primary" type="submit" :disabled="busy || !recoveryCodeValid">
        {{ loading ? 'Code wird geprüft …' : 'Wiederherstellungscode bestätigen' }}
      </button>
    </form>

    <p v-else class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-950" role="status">
      Keine der eingerichteten Sicherheitsmethoden kann in diesem Browser verwendet werden.
    </p>

    <p v-if="error" id="mfa-error" class="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" role="alert" aria-live="assertive">{{ error }}</p>

    <div v-if="otherMethods.length" class="border-t border-slate-200 pt-4" aria-labelledby="other-mfa-methods">
      <p id="other-mfa-methods" class="mb-3 text-sm font-semibold text-slate-700">Andere Sicherheitsmethode verwenden</p>
      <div class="grid gap-2" data-mfa-method-options>
        <button
          v-for="method in otherMethods"
          :key="method"
          class="group flex min-h-16 min-w-0 w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition-colors hover:border-[#8baabd] hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="busy"
          :aria-label="methodLabel(method)"
          :aria-describedby="methodDescriptionId(method)"
          data-mfa-method-option
          @click="selectMethod(method)"
        >
          <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-[#154d73] transition-colors group-hover:bg-[#e2edf4]" aria-hidden="true">
            <component :is="methodIcon(method)" class="size-5" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block font-bold text-slate-950">{{ methodTitle(method) }}</span>
            <span :id="methodDescriptionId(method)" class="mt-0.5 block text-xs leading-5 text-slate-600">{{ methodDescription(method) }}</span>
          </span>
          <ChevronRight class="size-5 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-[#154d73]" aria-hidden="true" />
        </button>
      </div>
    </div>

    <button class="inline-flex min-h-11 items-center justify-center gap-2 text-sm font-semibold text-slate-600 hover:text-[#154d73] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] disabled:cursor-not-allowed disabled:opacity-50" type="button" :disabled="busy" @click="$emit('back')">
      <ArrowLeft class="size-4" aria-hidden="true" /> Zurück zur Anmeldung
    </button>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ChevronRight, KeyRound, LifeBuoy, ShieldCheck } from 'lucide-vue-next'
import { ApiError } from '~/composables/useApi'
import type { MfaMethod } from '~/types/auth'
import { formatRecoveryCode, normalizeRecoveryCode, preferredAvailableMethod } from '~/utils/mfa'
import { isPasskeySupported, PasskeyBrowserError } from '~/utils/webauthn'

const emit = defineEmits<{
  back: []
  expired: [message: string]
}>()
const props = withDefaults(defineProps<{
  redirectTarget?: string
  replaceNavigation?: boolean
}>(), {
  redirectTarget: '/',
  replaceNavigation: false
})

const authStore = useAuthStore()
const activeMethod = ref<MfaMethod | null>(null)
const passkeySupported = ref(false)
const passkeyLoading = ref(false)
const loading = ref(false)
const passkeyNotice = ref('')
const error = ref('')
const code = ref('')
const recoveryCode = ref('')
const otpInput = ref<{ focus: () => void } | null>(null)
const busy = computed(() => loading.value || passkeyLoading.value)
const recoveryCodeValid = computed(() => normalizeRecoveryCode(recoveryCode.value).length === 12)
const usableMethods = computed(() => (authStore.mfaChallenge?.methods || [])
  .filter(method => method !== 'passkey' || passkeySupported.value))
const otherMethods = computed(() => usableMethods.value.filter(method => method !== activeMethod.value))
const fatalCodes = new Set([
  'MFA_CHALLENGE_EXPIRED',
  'MFA_CHALLENGE_INVALID',
  'MFA_CHALLENGE_USED',
  'MFA_CHALLENGE_MISSING',
  'MFA_TOO_MANY_ATTEMPTS'
])

onMounted(() => {
  passkeySupported.value = isPasskeySupported()
  const challenge = authStore.mfaChallenge
  if (!challenge) return
  activeMethod.value = preferredAvailableMethod(
    challenge.methods,
    challenge.preferredMethod,
    passkeySupported.value
  )
  focusActiveInput()
})

watch(recoveryCode, (value) => {
  const formatted = formatRecoveryCode(value)
  if (formatted !== value) recoveryCode.value = formatted
})

function methodLabel(method: MfaMethod): string {
  return {
    passkey: 'Passkey verwenden',
    totp: 'Authenticator-App verwenden',
    recovery_code: 'Wiederherstellungscode verwenden'
  }[method]
}

function methodTitle(method: MfaMethod): string {
  return {
    passkey: 'Passkey',
    totp: 'Authenticator-App',
    recovery_code: 'Wiederherstellungscode'
  }[method]
}

function methodDescription(method: MfaMethod): string {
  return {
    passkey: 'Mit Gerät oder Sicherheitsschlüssel bestätigen',
    totp: 'Sechsstelligen Code aus Ihrer Authenticator-App eingeben',
    recovery_code: 'Einen gespeicherten Wiederherstellungscode verwenden'
  }[method]
}

function methodIcon(method: MfaMethod) {
  return { passkey: KeyRound, totp: ShieldCheck, recovery_code: LifeBuoy }[method]
}

function methodDescriptionId(method: MfaMethod): string {
  return `mfa-method-${method}-description`
}

function focusActiveInput() {
  nextTick(() => {
    if (activeMethod.value === 'totp') otpInput.value?.focus()
    if (activeMethod.value === 'recovery_code') {
      document.getElementById('mfa-recovery-code')?.focus()
    }
  })
}

function selectMethod(method: MfaMethod) {
  activeMethod.value = method
  error.value = ''
  code.value = ''
  recoveryCode.value = ''
  focusActiveInput()
}

function handleError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && fatalCodes.has(cause.code || '')) {
    emit('expired', cause.message)
    return
  }
  error.value = cause instanceof Error ? cause.message : fallback
}

async function submitPasskey() {
  if (busy.value) return
  passkeyLoading.value = true
  passkeyNotice.value = ''
  error.value = ''
  try {
    await authStore.verifyMfaWithPasskey()
    await navigateTo(props.redirectTarget, { replace: props.replaceNavigation })
  } catch (cause) {
    if (cause instanceof PasskeyBrowserError) {
      passkeyNotice.value = cause.message
    } else {
      handleError(cause, 'Der Passkey konnte nicht geprüft werden.')
    }
  } finally {
    passkeyLoading.value = false
  }
}

async function submitCode() {
  if (busy.value || !activeMethod.value || activeMethod.value === 'passkey') return
  loading.value = true
  error.value = ''
  try {
    const recovery = activeMethod.value === 'recovery_code'
    await authStore.verifyMfa(recovery ? recoveryCode.value : code.value, recovery)
    await navigateTo(props.redirectTarget, { replace: props.replaceNavigation })
  } catch (cause) {
    handleError(cause, 'Der Code konnte nicht geprüft werden.')
    if (activeMethod.value === 'totp') code.value = ''
    focusActiveInput()
  } finally {
    loading.value = false
  }
}
</script>
