<template>
  <section class="rounded-2xl border border-rose-200 bg-rose-50/40 p-5 sm:p-7" aria-labelledby="account-danger-heading">
    <h2 id="account-danger-heading" class="text-lg font-bold text-rose-950">Gefahrenbereich</h2>
    <p class="mt-2 text-sm leading-6 text-rose-900">Hier kannst du dein Konto stilllegen oder dauerhaft entfernen. Prüfe sorgfältig, welche Aktion du auswählst.</p>

    <div class="mt-6 grid gap-6">
      <div class="rounded-xl border border-amber-200 bg-white p-4 sm:p-5">
        <h3 class="font-bold text-slate-950">Konto deaktivieren</h3>
        <p class="mt-2 text-sm leading-6 text-slate-700">Der Login wird sofort gesperrt. Deine Daten und bisherigen Beiträge bleiben erhalten. Eine Reaktivierung ist über die Administration möglich.</p>
        <Button class="mt-4 w-full border-amber-300 text-amber-900 hover:bg-amber-50 sm:w-auto" @click="deactivateOpen = true">
          <UserRoundX class="size-4" aria-hidden="true" /> Konto deaktivieren
        </Button>
      </div>

      <div class="rounded-xl border border-rose-300 bg-white p-4 sm:p-5">
        <h3 class="font-bold text-rose-950">Konto dauerhaft löschen</h3>
        <p class="mt-2 text-sm leading-6 text-slate-700">Deine persönlichen Kontodaten werden dauerhaft gelöscht. Öffentliche fachliche Beiträge können ohne Kontozuordnung erhalten bleiben. Diese Aktion kann nicht rückgängig gemacht werden.</p>
        <Button class="mt-4 w-full sm:w-auto" variant="danger" @click="deleteWarningOpen = true">
          <Trash2 class="size-4" aria-hidden="true" /> Konto dauerhaft löschen
        </Button>
      </div>
    </div>

    <AppConfirmDialog
      v-model:open="deactivateOpen"
      title="Konto deaktivieren?"
      description="Du wirst sofort auf allen Geräten abgemeldet."
      body="Deine Daten und bisherigen Beiträge bleiben erhalten. Eine Reaktivierung ist über die Administration möglich."
      confirm-label="Konto deaktivieren"
      loading-label="Konto wird deaktiviert …"
      variant="warning"
      :loading="deactivateLoading"
      :error="deactivateError"
      @confirm="deactivateAccount"
    />

    <AppConfirmDialog
      v-model:open="deleteWarningOpen"
      title="Konto dauerhaft löschen?"
      description="Diese Aktion ist endgültig."
      body="Deine persönlichen Kontodaten werden gelöscht, du wirst auf allen Geräten abgemeldet und kannst dieses Konto nicht wiederherstellen. Öffentliche fachliche Beiträge können anonymisiert erhalten bleiben."
      confirm-label="Weiter"
      variant="danger"
      @confirm="continueDeletion"
    />

    <AppModal
      v-model:open="deleteConfirmOpen"
      title="Löschung bestätigen"
      description="Bitte gib zur Bestätigung LÖSCHEN ein. Groß- und Kleinschreibung werden nicht unterschieden."
      described-by="account-delete-confirmation-help"
      size="sm"
      role="alertdialog"
      :busy="deleteLoading"
      :show-close="false"
    >
      <div class="grid gap-4">
        <label>
          <span class="field-label">Bestätigungstext</span>
          <input
            v-model="confirmationText"
            class="field-input"
            autocomplete="off"
            :disabled="deleteLoading"
            data-autofocus
            aria-describedby="account-delete-confirmation-help"
          >
        </label>
        <p id="account-delete-confirmation-help" class="text-sm leading-6 text-slate-600">Bei einem Passwortkonto ist zusätzlich das aktuelle Passwort erforderlich. Konten mit ausschließlich externer Anmeldung benötigen eine aktuelle Sitzung.</p>
        <label>
          <span class="field-label">Aktuelles Passwort <span class="font-normal">(falls vorhanden)</span></span>
          <input v-model="currentPassword" class="field-input" type="password" autocomplete="current-password" :disabled="deleteLoading">
        </label>
        <p v-if="deleteError" class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800" role="alert">{{ deleteError }}</p>
      </div>

      <template #footer>
        <div class="flex flex-col gap-3 sm:flex-row sm:justify-end">
          <Button :disabled="deleteLoading" @click="cancelDeletion">Abbrechen</Button>
          <Button variant="danger" :disabled="!deleteConfirmationValid || deleteLoading" @click="deleteAccount">
            <LoaderCircle v-if="deleteLoading" class="size-4 animate-spin" aria-hidden="true" />
            {{ deleteLoading ? 'Konto wird gelöscht …' : 'Konto endgültig löschen' }}
          </Button>
        </div>
      </template>
    </AppModal>
  </section>
</template>

<script setup lang="ts">
import { LoaderCircle, Trash2, UserRoundX } from 'lucide-vue-next'
import { ApiError } from '~/composables/useApi'

const authStore = useAuthStore()
const router = useRouter()
const deactivateOpen = ref(false)
const deactivateLoading = ref(false)
const deactivateError = ref('')
const deleteWarningOpen = ref(false)
const deleteConfirmOpen = ref(false)
const deleteLoading = ref(false)
const deleteError = ref('')
const confirmationText = ref('')
const currentPassword = ref('')
const deleteConfirmationValid = computed(() => confirmationText.value.trim().toLocaleUpperCase('de-DE') === 'LÖSCHEN')

async function deactivateAccount() {
  if (deactivateLoading.value) return
  deactivateLoading.value = true
  deactivateError.value = ''
  try {
    await authStore.deactivateAccount()
    deactivateOpen.value = false
    await router.push('/login?account=deactivated')
  } catch (error) {
    deactivateError.value = accountErrorMessage(error, 'Das Konto konnte nicht deaktiviert werden. Bitte versuche es erneut.')
  } finally {
    deactivateLoading.value = false
  }
}

function continueDeletion() {
  deleteWarningOpen.value = false
  confirmationText.value = ''
  currentPassword.value = ''
  deleteError.value = ''
  deleteConfirmOpen.value = true
}

function cancelDeletion() {
  if (deleteLoading.value) return
  deleteConfirmOpen.value = false
  confirmationText.value = ''
  currentPassword.value = ''
  deleteError.value = ''
}

async function deleteAccount() {
  if (!deleteConfirmationValid.value || deleteLoading.value) return
  deleteLoading.value = true
  deleteError.value = ''
  try {
    await authStore.deleteAccount(confirmationText.value, currentPassword.value)
    deleteConfirmOpen.value = false
    await router.push('/login?account=deleted')
  } catch (error) {
    deleteError.value = accountErrorMessage(error, 'Das Konto konnte nicht gelöscht werden. Bitte versuche es erneut.')
  } finally {
    deleteLoading.value = false
  }
}

function accountErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.code === 'LAST_SUPERUSER_REQUIRED') {
    return 'Dieses Konto ist der letzte aktive Superuser und kann daher nicht deaktiviert oder gelöscht werden.'
  }
  if (error instanceof ApiError && ['INVALID_CURRENT_PASSWORD', 'RECENT_AUTH_REQUIRED', 'INVALID_DELETE_CONFIRMATION'].includes(error.code || '')) {
    return error.message
  }
  return fallback
}
</script>
