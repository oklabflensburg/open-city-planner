<template>
  <Card class="p-5 sm:p-7">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-slate-950">Passkeys</h2>
        <p class="mt-1 text-sm leading-6 text-slate-600">Ein Passkey ermöglicht eine sichere Anmeldung mit Geräte-PIN, Biometrie oder Sicherheitsschlüssel.</p>
      </div>
      <StatusBadge :tone="passkeys.length ? 'success' : 'neutral'">{{ passkeys.length ? `${passkeys.length} aktiv` : 'Nicht eingerichtet' }}</StatusBadge>
    </div>
    <p class="mt-3 text-xs leading-5 text-slate-500">Biometrische Daten werden nicht an den Stadtplaner übertragen.</p>
    <p v-if="!supported" class="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900" role="status">Passkeys werden von diesem Browser nicht unterstützt.</p>
    <p v-if="error" class="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-slate-600" role="status">Passkeys werden geladen …</p>
    <ul v-else-if="passkeys.length" class="mt-5 divide-y divide-slate-200" aria-label="Registrierte Passkeys">
      <li v-for="passkey in passkeys" :key="passkey.id" class="py-4 first:pt-0 last:pb-0">
        <form v-if="editingId === passkey.id" class="grid gap-3 sm:grid-cols-[1fr_auto_auto]" @submit.prevent="saveName(passkey.id)">
          <FormField :id="`passkey-name-${passkey.id}`" v-model="editingName" label="Passkey-Name" required :disabled="actionLoading" />
          <button class="page-button-primary self-end" type="submit" :disabled="actionLoading || !editingName.trim()">Speichern</button>
          <button class="page-button-secondary self-end" type="button" @click="editingId = null">Abbrechen</button>
        </form>
        <div v-else class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 class="font-bold text-slate-950">{{ passkey.name }}</h3>
            <p class="mt-1 text-sm text-slate-600">Hinzugefügt: {{ formatDate(passkey.created_at) }} · Zuletzt verwendet: {{ formatDate(passkey.last_used_at) }}</p>
            <p v-if="passkey.device_type === 'multi_device' || passkey.backed_up" class="mt-1 text-xs font-semibold text-[#154d73]">Synchronisierter Passkey</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="page-button-secondary" type="button" @click="edit(passkey)">Umbenennen</button>
            <button class="page-button-danger" type="button" :disabled="actionLoading" @click="removeTarget = passkey">Entfernen</button>
          </div>
        </div>
      </li>
    </ul>
    <form v-if="supported" class="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]" @submit.prevent="addPasskey">
      <FormField id="new-passkey-name" v-model="newName" label="Name des neuen Passkeys (optional)" autocomplete="off" :disabled="actionLoading" />
      <button class="page-button-primary self-end" type="submit" :disabled="actionLoading">{{ actionLoading ? 'Passkey wird eingerichtet …' : 'Passkey hinzufügen' }}</button>
    </form>
    <p v-if="passkeys.length === 1" class="mt-4 text-sm leading-6 text-slate-600">Fügen Sie optional einen weiteren Passkey auf einem anderen Gerät oder Sicherheitsschlüssel hinzu.</p>
    <AppConfirmDialog
      :open="Boolean(removeTarget)"
      title="Passkey entfernen?"
      :body="removeTarget ? `Der Passkey „${removeTarget.name}“ kann danach auf diesem Konto nicht mehr verwendet werden.` : ''"
      confirm-label="Passkey entfernen"
      loading-label="Passkey wird entfernt …"
      variant="danger"
      :loading="actionLoading"
      :error="removeError"
      @update:open="value => { if (!value) removeTarget = null }"
      @confirm="confirmRemove"
    />
  </Card>
</template>

<script setup lang="ts">
import type { Passkey } from '~/types/auth'
import { isPasskeySupported } from '~/utils/webauthn'

const authStore = useAuthStore()
const supported = ref(false)
const loading = ref(true)
const actionLoading = ref(false)
const error = ref('')
const newName = ref('')
const editingId = ref<string | null>(null)
const editingName = ref('')
const removeTarget = ref<Passkey | null>(null)
const removeError = ref('')
const passkeys = computed(() => authStore.passkeys)

onMounted(async () => {
  supported.value = isPasskeySupported()
  try {
    await authStore.loadPasskeys()
  } catch (err) {
    error.value = message(err)
  } finally {
    loading.value = false
  }
})

async function addPasskey() {
  actionLoading.value = true
  error.value = ''
  try {
    await authStore.registerPasskey(newName.value.trim() || undefined)
    newName.value = ''
  } catch (err) {
    error.value = message(err)
  } finally {
    actionLoading.value = false
  }
}

function edit(passkey: Passkey) {
  editingId.value = passkey.id
  editingName.value = passkey.name
}

async function saveName(id: string) {
  actionLoading.value = true
  error.value = ''
  try {
    await authStore.renamePasskey(id, editingName.value.trim())
    editingId.value = null
  } catch (err) {
    error.value = message(err)
  } finally {
    actionLoading.value = false
  }
}

async function confirmRemove() {
  if (!removeTarget.value) return
  actionLoading.value = true
  removeError.value = ''
  try {
    await authStore.deletePasskey(removeTarget.value.id)
    removeTarget.value = null
  } catch (err) {
    removeError.value = message(err)
  } finally {
    actionLoading.value = false
  }
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(new Date(value)) : 'Noch nicht verwendet'
}

function message(err: unknown) {
  return err instanceof Error ? err.message : 'Die Passkey-Einstellung konnte nicht verarbeitet werden.'
}
</script>
