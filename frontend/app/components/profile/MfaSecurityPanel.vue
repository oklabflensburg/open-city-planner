<template>
  <Card class="p-5 sm:p-7">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div><h2 class="text-lg font-bold text-slate-950">Zwei-Faktor-Authentifizierung</h2><p class="mt-1 text-sm text-slate-600">{{ status?.enabled ? 'Aktiviert' : 'Nicht aktiviert' }}</p></div>
      <StatusBadge :tone="status?.enabled ? 'success' : 'neutral'">{{ status?.enabled ? 'Aktiviert' : 'Inaktiv' }}</StatusBadge>
    </div>
    <p v-if="loading" class="mt-4 text-sm text-slate-600" role="status">Sicherheitsstatus wird geladen …</p>
    <p v-else-if="error" class="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
    <template v-else-if="setup && !recoveryCodes.length">
      <div class="mt-5 grid gap-5 sm:grid-cols-[180px_1fr]">
        <img v-if="qrDataUrl" :src="qrDataUrl" class="size-44 rounded-xl border border-slate-200" alt="QR-Code zur Einrichtung der Authenticator-App">
        <div class="min-w-0"><p class="text-sm leading-6 text-slate-700">Scannen Sie den QR-Code lokal mit Ihrer Authenticator-App oder geben Sie den Schlüssel manuell ein.</p><p class="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Manueller Einrichtungsschlüssel</p><code class="mt-1 block break-all rounded-lg bg-slate-100 p-3 text-sm">{{ setup.secret }}</code><button class="mt-2 text-sm font-semibold text-[#154d73]" type="button" @click="copy(setup.secret)">Schlüssel kopieren</button></div>
      </div>
      <form class="mt-5 grid gap-4" @submit.prevent="confirmSetup"><OtpInput v-model="confirmationCode" :disabled="actionLoading" /><button class="page-button-primary" type="submit" :disabled="actionLoading || confirmationCode.length !== 6">Einrichtung bestätigen</button><button class="text-sm font-semibold text-slate-600" type="button" @click="cancelSetup">Abbrechen</button></form>
    </template>
    <template v-else-if="recoveryCodes.length">
      <div class="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4"><h3 class="font-bold text-slate-950">Wiederherstellungscodes speichern</h3><p class="mt-1 text-sm leading-6 text-slate-700">Jeder Code kann nur einmal verwendet werden. Diese Liste wird nicht erneut angezeigt.</p><ul class="mt-4 grid gap-2 font-mono text-sm sm:grid-cols-2" aria-label="Wiederherstellungscodes"><li v-for="item in recoveryCodes" :key="item"><code>{{ item }}</code></li></ul><div class="mt-4 flex flex-wrap gap-3"><button class="page-button-secondary" type="button" @click="copy(recoveryCodes.join('\n'))">Alle kopieren</button><button class="page-button-secondary" type="button" @click="downloadCodes">Als .txt herunterladen</button></div><label class="mt-4 flex items-start gap-2 text-sm text-slate-700"><input v-model="codesSaved" class="mt-1 accent-[#154d73]" type="checkbox">Ich habe meine Wiederherstellungscodes gespeichert.</label><button class="page-button-primary mt-4" type="button" :disabled="!codesSaved" @click="finishCodes">Abschließen</button></div>
    </template>
    <template v-else-if="status?.enabled">
      <dl class="mt-5 grid gap-3 text-sm sm:grid-cols-2"><div><dt class="font-semibold text-slate-500">Methode</dt><dd>Authenticator-App</dd></div><div><dt class="font-semibold text-slate-500">Eingerichtet am</dt><dd>{{ formatDate(status.enabled_at) }}</dd></div><div><dt class="font-semibold text-slate-500">Zuletzt verwendet</dt><dd>{{ formatDate(status.last_used_at) }}</dd></div><div><dt class="font-semibold text-slate-500">Verbleibende Codes</dt><dd>{{ status.recovery_codes_remaining }}</dd></div></dl>
      <div class="mt-5 flex flex-wrap gap-3"><button class="page-button-secondary" type="button" @click="action = 'regenerate'">Wiederherstellungscodes erneuern</button><button class="page-button-danger" type="button" @click="action = 'disable'">Zwei-Faktor-Authentifizierung deaktivieren</button></div>
      <form v-if="action" class="mt-5 grid gap-4 rounded-xl border border-slate-200 p-4" @submit.prevent="submitSensitiveAction"><h3 class="font-bold">{{ action === 'disable' ? '2FA sicher deaktivieren' : 'Neue Codes erzeugen' }}</h3><FormField id="mfa-current-password" v-model="currentPassword" label="Aktuelles Passwort (bei Passwortkonten)" type="password" autocomplete="current-password" :disabled="actionLoading" /><OtpInput v-if="!useActionRecovery" v-model="actionCode" :disabled="actionLoading" /><FormField v-else id="mfa-action-recovery" v-model="actionRecoveryCode" label="Wiederherstellungscode" autocomplete="one-time-code" :disabled="actionLoading" /><button class="text-left text-sm font-semibold text-[#154d73]" type="button" @click="useActionRecovery = !useActionRecovery">{{ useActionRecovery ? 'Authenticator-Code verwenden' : 'Wiederherstellungscode verwenden' }}</button><div class="flex flex-wrap gap-3"><button :class="action === 'disable' ? 'page-button-danger' : 'page-button-primary'" type="submit" :disabled="actionLoading || (!useActionRecovery && actionCode.length !== 6) || (useActionRecovery && !actionRecoveryCode)">Bestätigen</button><button class="page-button-secondary" type="button" @click="action = null">Abbrechen</button></div></form>
    </template>
    <template v-else><p class="mt-4 text-sm leading-6 text-slate-700">Schützen Sie Ihr Konto zusätzlich mit einer Authenticator-App.</p><button class="page-button-primary mt-4" type="button" :disabled="actionLoading" @click="beginSetup">Zwei-Faktor-Authentifizierung einrichten</button></template>
  </Card>
</template>

<script setup lang="ts">
import QRCode from 'qrcode'
import type { MfaSecurityStatus, TotpSetup } from '~/types/auth'

const authStore = useAuthStore()
const status = ref<MfaSecurityStatus | null>(null)
const setup = ref<TotpSetup | null>(null)
const qrDataUrl = ref('')
const confirmationCode = ref('')
const recoveryCodes = ref<string[]>([])
const codesSaved = ref(false)
const loading = ref(true)
const actionLoading = ref(false)
const error = ref('')
const action = ref<'disable' | 'regenerate' | null>(null)
const currentPassword = ref('')
const actionCode = ref('')
const actionRecoveryCode = ref('')
const useActionRecovery = ref(false)

onMounted(loadStatus)
async function loadStatus() { loading.value = true; try { status.value = await authStore.loadMfaSecurity() } catch (err) { error.value = message(err) } finally { loading.value = false } }
async function beginSetup() { actionLoading.value = true; error.value = ''; try { setup.value = await authStore.startTotpSetup(); qrDataUrl.value = await QRCode.toDataURL(setup.value.otpauth_uri, { width: 352, margin: 2, errorCorrectionLevel: 'M' }) } catch (err) { error.value = message(err) } finally { actionLoading.value = false } }
async function confirmSetup() { actionLoading.value = true; error.value = ''; try { recoveryCodes.value = (await authStore.confirmTotpSetup(confirmationCode.value)).recovery_codes; setup.value = null } catch (err) { error.value = message(err) } finally { actionLoading.value = false } }
async function submitSensitiveAction() { if (!action.value) return; actionLoading.value = true; error.value = ''; const factor = useActionRecovery.value ? { recovery_code: actionRecoveryCode.value } : { code: actionCode.value }; try { if (action.value === 'regenerate') { recoveryCodes.value = (await authStore.regenerateRecoveryCodes({ current_password: currentPassword.value || undefined, ...factor })).recovery_codes; action.value = null } else { await authStore.disableMfa({ current_password: currentPassword.value || undefined, ...factor }); await navigateTo('/login') } } catch (err) { error.value = message(err) } finally { actionLoading.value = false } }
function cancelSetup() { setup.value = null; qrDataUrl.value = ''; confirmationCode.value = '' }
async function finishCodes() { recoveryCodes.value = []; codesSaved.value = false; await loadStatus() }
async function copy(value: string) { await navigator.clipboard.writeText(value) }
function downloadCodes() { const blob = new Blob([`Stadtplaner Wiederherstellungscodes\n\n${recoveryCodes.value.join('\n')}\n`], { type: 'text/plain;charset=utf-8' }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'stadtplaner-wiederherstellungscodes.txt'; anchor.click(); URL.revokeObjectURL(url) }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('de-DE').format(new Date(value)) : 'Noch nicht verwendet' }
function message(err: unknown) { return err instanceof Error ? err.message : 'Die Sicherheitseinstellung konnte nicht verarbeitet werden.' }
</script>
