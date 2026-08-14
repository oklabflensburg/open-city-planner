<template>
  <AppModal
    :open="true"
    title="Benutzerkonto verwalten"
    description="Rollen, Zugriffsstatus und Kontodaten prüfen."
    size="lg"
    :busy="mutationLoading"
    @close="$emit('close')"
  >
    <div class="flex min-w-0 items-center gap-4">
      <UserAvatar :user="user" size="lg" loading="eager" />
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-xl font-bold text-slate-950">{{ displayName }}</h3>
          <StatusBadge v-if="user.is_superuser" tone="warning">SUPERUSER</StatusBadge>
        </div>
        <p class="mt-1 break-all text-sm text-slate-600">{{ user.email }}</p>
      </div>
    </div>

    <dl class="mt-6 grid gap-4 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2">
      <div><dt class="font-semibold text-slate-500">Kontostatus</dt><dd class="mt-1 font-bold text-slate-900">{{ user.is_active ? 'Aktiv' : 'Inaktiv' }}</dd></div>
      <div><dt class="font-semibold text-slate-500">E-Mail bestätigt</dt><dd class="mt-1 font-bold text-slate-900">{{ user.is_verified ? 'Ja' : 'Nein' }}</dd></div>
      <div><dt class="font-semibold text-slate-500">Registriert</dt><dd class="mt-1 font-bold text-slate-900">{{ formatDate(user.created_at) }}</dd></div>
      <div><dt class="font-semibold text-slate-500">Letzter Login</dt><dd class="mt-1 font-bold text-slate-900">{{ formatDate(user.last_login_at) }}</dd></div>
      <div class="sm:col-span-2"><dt class="font-semibold text-slate-500">Anmeldeanbieter</dt><dd class="mt-1 font-bold text-slate-900">{{ user.oauth_providers.length ? user.oauth_providers.join(', ') : 'Passwortkonto oder keine Verknüpfung' }}</dd></div>
    </dl>

    <div v-if="user.is_superuser" class="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
      Superuser-Rechte werden hier nur angezeigt und können nicht über die normale Rollenverwaltung geändert werden.
    </div>

    <div class="mt-6">
      <h3 class="font-bold text-slate-950">Rollen</h3>
      <p class="mt-1 text-sm text-slate-600">Änderungen werden nach Bestätigung unmittelbar serverseitig gespeichert.</p>
      <div class="mt-4 space-y-3">
        <label v-for="role in roles" :key="role.name" class="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4 hover:bg-slate-50">
          <input
            type="checkbox"
            class="mt-1 size-5 accent-[#154d73]"
            :checked="user.roles.includes(role.name)"
            :disabled="mutationLoading"
            @click.prevent="requestRoleChange(role.name, !user.roles.includes(role.name))"
          >
          <span><strong class="text-sm text-slate-950">{{ role.name }}</strong><span class="mt-1 block text-sm leading-6 text-slate-600">{{ role.description }}</span><span v-if="mutationKey === `${user.id}:${role.name}`" class="mt-1 block text-xs font-semibold text-[#154d73]">Wird aktualisiert …</span></span>
        </label>
      </div>
    </div>

    <div class="mt-7 border-t border-slate-200 pt-6">
      <h3 class="font-bold text-slate-950">Kontozugriff</h3>
      <p class="mt-1 text-sm leading-6 text-slate-600">Deaktivierte Konten können sich nicht anmelden; bestehende Sitzungen werden widerrufen.</p>
      <Button
        class="mt-4"
        :variant="user.is_active ? 'danger' : 'secondary'"
        :disabled="user.id === currentUserId || mutationLoading"
        @click="requestStatusChange"
      >
        {{ user.is_active ? 'Konto deaktivieren' : 'Konto aktivieren' }}
      </Button>
      <p v-if="user.id === currentUserId" class="mt-2 text-xs text-slate-500">Das aktuell verwendete eigene Konto kann nicht deaktiviert werden.</p>
    </div>

    <AppConfirmDialog
      :open="Boolean(pendingAction)"
      :title="confirmationTitle"
      :body="confirmationBody"
      :confirm-label="confirmationLabel"
      :variant="confirmationVariant"
      :loading="mutationLoading"
      :error="confirmationStarted ? mutationError : ''"
      @update:open="closeConfirmation"
      @confirm="confirmAction"
      @cancel="closeConfirmation"
    />
  </AppModal>
</template>

<script setup lang="ts">
import type { AdminRole, AdminUser } from '~/types/admin'

type PendingAction =
  | { type: 'role', role: string, enabled: boolean }
  | { type: 'status', active: boolean }

const props = defineProps<{
  user: AdminUser
  roles: AdminRole[]
  currentUserId?: string
  mutationKey: string
  mutationError?: string
}>()
const emit = defineEmits<{
  close: []
  toggleRole: [role: string, enabled: boolean]
  toggleStatus: [active: boolean]
}>()

const pendingAction = ref<PendingAction | null>(null)
const confirmationStarted = ref(false)
const displayName = computed(() => props.user.display_name || [props.user.first_name, props.user.last_name].filter(Boolean).join(' ') || props.user.email)
const mutationLoading = computed(() => Boolean(props.mutationKey))
const confirmationTitle = computed(() => {
  if (pendingAction.value?.type === 'role') return `Rolle ${pendingAction.value.role} ${pendingAction.value.enabled ? 'vergeben' : 'entfernen'}?`
  return pendingAction.value?.active ? 'Konto aktivieren?' : 'Konto deaktivieren?'
})
const confirmationBody = computed(() => {
  if (pendingAction.value?.type === 'role') {
    return pendingAction.value.role === 'VERWALTUNG'
      ? pendingAction.value.enabled
        ? 'Dieser Benutzer erhält Zugriff auf interne Verwaltungsdaten und erweiterte Bearbeitungsrechte.'
        : 'Dieser Benutzer verliert den Zugriff auf Verwaltungsdaten und die entsprechenden erweiterten Bearbeitungsrechte.'
      : `Die Rollen des Kontos „${displayName.value}“ werden unmittelbar geändert.`
  }
  return pendingAction.value?.active
    ? `Das Konto „${displayName.value}“ kann sich anschließend wieder anmelden.`
    : `Das Konto „${displayName.value}“ kann sich nicht mehr anmelden; bestehende Sitzungen werden widerrufen.`
})
const confirmationLabel = computed(() => {
  if (pendingAction.value?.type === 'role') return pendingAction.value.enabled ? 'Rolle vergeben' : 'Rolle entfernen'
  return pendingAction.value?.active ? 'Konto aktivieren' : 'Konto deaktivieren'
})
const confirmationVariant = computed<'warning' | 'danger'>(() => {
  if (pendingAction.value?.type === 'status' && !pendingAction.value.active) return 'danger'
  return 'warning'
})

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Noch nie'
}

function requestRoleChange(role: string, enabled: boolean) {
  confirmationStarted.value = false
  pendingAction.value = { type: 'role', role, enabled }
}

function requestStatusChange() {
  confirmationStarted.value = false
  pendingAction.value = { type: 'status', active: !props.user.is_active }
}

function confirmAction() {
  if (!pendingAction.value || mutationLoading.value) return
  confirmationStarted.value = true
  if (pendingAction.value.type === 'role') emit('toggleRole', pendingAction.value.role, pendingAction.value.enabled)
  else emit('toggleStatus', pendingAction.value.active)
}

function closeConfirmation(open = false) {
  if (open || mutationLoading.value) return
  pendingAction.value = null
  confirmationStarted.value = false
}

watch(() => props.mutationKey, async (current, previous) => {
  if (!confirmationStarted.value || !previous || current) return
  await nextTick()
  const action = pendingAction.value
  const applied = action?.type === 'role'
    ? props.user.roles.includes(action.role) === action.enabled
    : action?.type === 'status' && props.user.is_active === action.active
  if (applied) closeConfirmation()
})
</script>
