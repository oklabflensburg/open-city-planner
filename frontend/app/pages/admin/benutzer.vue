<template>
  <ContentPageShell
    title="Benutzer & Rollen"
    description="Benutzerkonten durchsuchen, Zugriffsrollen verwalten und Kontostatus prüfen."
    eyebrow="Administration"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Administration' }, { label: 'Benutzer' }]"
    max-width="wide"
  >
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>

    <Card class="p-5 sm:p-6">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_15rem_12rem]">
        <label><span class="field-label">Benutzer suchen</span><span class="relative block"><Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><input v-model="search" type="search" class="field-input pl-10" placeholder="Name oder E-Mail" autocomplete="off"></span></label>
        <label><span class="field-label">Rolle</span><select v-model="role" class="field-input"><option value="">Alle Rollen</option><option v-for="item in roles" :key="item.name" :value="item.name">{{ item.name }}</option></select></label>
        <label><span class="field-label">Status</span><select v-model="active" class="field-input"><option value="all">Alle Konten</option><option value="active">Aktiv</option><option value="inactive">Inaktiv</option></select></label>
      </div>
    </Card>

    <div class="mt-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm font-semibold text-slate-600" aria-live="polite">{{ total }} {{ total === 1 ? 'Benutzerkonto' : 'Benutzerkonten' }}</p>
      <Button v-if="search || role || active !== 'all'" @click="resetFilters"><RotateCcw class="size-4" /> Filter zurücksetzen</Button>
    </div>

    <p v-if="success" class="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900" role="status">{{ success }}</p>
    <p v-if="mutationError || error" class="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800" role="alert">{{ mutationError || error }}</p>

    <div v-if="loading" class="mt-5 space-y-3" role="status" aria-label="Benutzer werden geladen">
      <div v-for="index in 5" :key="index" class="h-20 animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
    <AdminUserList v-else-if="users.length" class="mt-5" :users="users" :current-user-id="authStore.user?.id" @manage="openUser" />
    <Card v-else class="mt-5 p-10 text-center"><Users class="mx-auto size-9 text-slate-400" /><h2 class="mt-4 text-lg font-bold text-slate-950">Keine Benutzer gefunden</h2><p class="mt-2 text-sm text-slate-600">Passen Sie Suche oder Filter an.</p></Card>

    <nav v-if="totalPages > 1" class="mt-6 flex items-center justify-between" aria-label="Seitennavigation">
      <Button :disabled="page <= 1 || loading" @click="changePage(page - 1)"><ChevronLeft class="size-4" /> Zurück</Button>
      <span class="text-sm font-semibold text-slate-600">Seite {{ page }} von {{ totalPages }}</span>
      <Button :disabled="page >= totalPages || loading" @click="changePage(page + 1)">Weiter <ChevronRight class="size-4" /></Button>
    </nav>

    <AdminUserDialog
      v-if="selectedUser"
      :user="selectedUser"
      :roles="roles"
      :current-user-id="authStore.user?.id"
      :mutation-key="mutationKey"
      :mutation-error="mutationError"
      @close="selectedUser = null"
      @toggle-role="toggleRole"
      @toggle-status="toggleStatus"
    />
  </ContentPageShell>
</template>

<script setup lang="ts">
import { ChevronLeft, ChevronRight, RotateCcw, Search, Users } from 'lucide-vue-next'
import type { AdminUser } from '~/types/admin'

definePageMeta({ middleware: 'superuser' })

const authStore = useAuthStore()
const {
  users, roles, total, page, pageSize, search, role, active, loading, mutationKey, error,
  loadRoles, loadUsers, loadUser, assignRole, removeRole, setActive
} = useAdminUsers()
const selectedUser = ref<AdminUser | null>(null)
const success = ref('')
const mutationError = ref('')
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
let searchTimer: ReturnType<typeof setTimeout> | undefined

async function openUser(user: AdminUser) {
  mutationError.value = ''
  try { selectedUser.value = await loadUser(user.id) } catch (caught) { mutationError.value = messageFrom(caught, 'Benutzerdetails konnten nicht geladen werden.') }
}

async function toggleRole(roleName: string, enabled: boolean) {
  if (!selectedUser.value) return
  success.value = ''
  mutationError.value = ''
  try {
    const user = selectedUser.value
    selectedUser.value = enabled ? await assignRole(user, roleName) : await removeRole(user, roleName)
    success.value = enabled ? `Rolle ${roleName} wurde ${displayName(user)} zugewiesen.` : `Rolle ${roleName} wurde entfernt.`
  } catch (caught) {
    mutationError.value = messageFrom(caught, 'Die Rollenänderung konnte nicht gespeichert werden.')
  }
}

async function toggleStatus(isActive: boolean) {
  if (!selectedUser.value) return
  success.value = ''
  mutationError.value = ''
  try {
    selectedUser.value = await setActive(selectedUser.value, isActive)
    success.value = `Das Konto wurde ${isActive ? 'aktiviert' : 'deaktiviert'}.`
  } catch (caught) {
    mutationError.value = messageFrom(caught, 'Der Kontostatus konnte nicht gespeichert werden.')
  }
}

function resetFilters() { search.value = ''; role.value = ''; active.value = 'all'; page.value = 1 }
function changePage(nextPage: number) { page.value = nextPage; loadUsers() }
function displayName(user: AdminUser) { return user.display_name || [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email }
function messageFrom(caught: unknown, fallback: string) { return caught instanceof Error ? caught.message : fallback }

watch(search, () => {
  page.value = 1
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(loadUsers, 400)
})
watch([role, active], () => { page.value = 1; loadUsers() })
onMounted(async () => {
  try { await loadRoles() } catch (caught) { mutationError.value = messageFrom(caught, 'Rollen konnten nicht geladen werden.') }
  await loadUsers()
})
onBeforeUnmount(() => { if (searchTimer) clearTimeout(searchTimer) })

usePageSeo({
  title: 'Benutzer & Rollen',
  description: 'Geschützte Rollenverwaltung für Superuser.',
  path: '/admin/benutzer',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
