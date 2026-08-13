<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[100] flex items-end justify-center bg-slate-950/40 p-0 sm:items-center sm:p-4" @mousedown.self="$emit('close')">
      <section
        ref="dialog"
        class="max-h-[95dvh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-2xl sm:rounded-2xl sm:p-7"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-user-dialog-title"
        tabindex="-1"
        @keydown="handleKeydown"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex min-w-0 items-center gap-4">
            <UserAvatar :user="user" size="lg" loading="eager" />
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2"><h2 id="admin-user-dialog-title" class="text-xl font-bold text-slate-950">{{ displayName }}</h2><StatusBadge v-if="user.is_superuser" tone="warning">SUPERUSER</StatusBadge></div>
              <p class="mt-1 break-all text-sm text-slate-600">{{ user.email }}</p>
            </div>
          </div>
          <button class="inline-flex size-11 shrink-0 items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#154d73]" type="button" aria-label="Dialog schließen" @click="$emit('close')"><X class="size-5" /></button>
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
                :disabled="mutationKey === `${user.id}:${role.name}`"
                @change="requestRoleChange(role.name, ($event.target as HTMLInputElement).checked)"
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
            :disabled="user.id === currentUserId || mutationKey === `${user.id}:status`"
            @click="requestStatusChange"
          >
            {{ user.is_active ? 'Konto deaktivieren' : 'Konto aktivieren' }}
          </Button>
          <p v-if="user.id === currentUserId" class="mt-2 text-xs text-slate-500">Das aktuell verwendete eigene Konto kann nicht deaktiviert werden.</p>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import type { AdminRole, AdminUser } from '~/types/admin'

const props = defineProps<{ user: AdminUser, roles: AdminRole[], currentUserId?: string, mutationKey: string }>()
const emit = defineEmits<{
  close: []
  toggleRole: [role: string, enabled: boolean]
  toggleStatus: [active: boolean]
}>()
const dialog = ref<HTMLElement | null>(null)
const displayName = computed(() => props.user.display_name || [props.user.first_name, props.user.last_name].filter(Boolean).join(' ') || props.user.email)

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Noch nie'
}

function requestRoleChange(role: string, enabled: boolean) {
  const action = enabled ? 'vergeben' : 'entfernen'
  if (role === 'VERWALTUNG' && !window.confirm(`Rolle VERWALTUNG ${action}?\n\nDiese Rolle gewährt Zugriff auf interne Verwaltungsdaten und erweiterte Bearbeitungsrechte.`)) return
  emit('toggleRole', role, enabled)
}

function requestStatusChange() {
  const next = !props.user.is_active
  if (window.confirm(`Konto wirklich ${next ? 'aktivieren' : 'deaktivieren'}?`)) emit('toggleStatus', next)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
  if (event.key !== 'Tab' || !dialog.value) return
  const focusable = [...dialog.value.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')]
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}

onMounted(() => { document.body.style.overflow = 'hidden'; nextTick(() => dialog.value?.focus()) })
onBeforeUnmount(() => { document.body.style.overflow = '' })
</script>
