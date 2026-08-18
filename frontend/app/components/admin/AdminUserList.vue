<template>
  <div>
    <div class="grid gap-4 md:hidden">
      <Card v-for="user in users" :key="user.id" class="p-4">
        <div class="flex items-start gap-3">
          <UserAvatar :user="user" size="md" />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <p class="font-bold text-slate-950">{{ displayName(user) }}</p>
              <StatusBadge v-if="user.id === currentUserId" tone="info">Eigenes Konto</StatusBadge>
              <StatusBadge v-if="user.is_superuser" tone="warning">SUPERUSER</StatusBadge>
            </div>
            <p class="mt-1 break-all text-sm text-slate-600">{{ user.email }}</p>
          </div>
        </div>
        <div class="mt-4 flex flex-wrap gap-2">
          <StatusBadge v-for="role in user.roles" :key="role" tone="neutral">{{ role }}</StatusBadge>
          <span v-if="!user.roles.length" class="text-sm text-slate-500">Keine Rollen</span>
          <StatusBadge :tone="user.is_active ? 'success' : 'danger'">{{ user.is_active ? 'Aktiv' : 'Inaktiv' }}</StatusBadge>
        </div>
        <Button class="mt-4 w-full" @click="$emit('manage', user)">Verwalten</Button>
      </Card>
    </div>

    <Card class="hidden overflow-hidden md:block">
      <div class="overflow-x-auto">
        <table class="w-full min-w-[860px] text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
            <tr><th class="px-5 py-4">Benutzer</th><th class="px-5 py-4">E-Mail</th><th class="px-5 py-4">Rollen</th><th class="px-5 py-4">Status</th><th class="px-5 py-4">Letzter Login</th><th class="px-5 py-4 text-right">Aktion</th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="user in users" :key="user.id" class="hover:bg-slate-50/70">
              <td class="px-5 py-4">
                <div class="flex items-center gap-3">
                  <UserAvatar :user="user" size="sm" />
                  <div><p class="font-bold text-slate-950">{{ displayName(user) }}</p><div class="mt-1 flex gap-1"><StatusBadge v-if="user.id === currentUserId" tone="info">Eigenes Konto</StatusBadge><StatusBadge v-if="user.is_superuser" tone="warning">SUPERUSER</StatusBadge></div></div>
                </div>
              </td>
              <td class="max-w-64 break-all px-5 py-4 text-slate-600" :title="user.email">{{ user.email }}</td>
              <td class="px-5 py-4"><div class="flex flex-wrap gap-1"><StatusBadge v-for="role in user.roles" :key="role">{{ role }}</StatusBadge><span v-if="!user.roles.length" class="text-slate-500">Keine Rollen</span></div></td>
              <td class="px-5 py-4"><StatusBadge :tone="user.is_active ? 'success' : 'danger'">{{ user.is_active ? 'Aktiv' : 'Inaktiv' }}</StatusBadge></td>
              <td class="px-5 py-4 text-slate-600">{{ formatDate(user.last_login_at) }}</td>
              <td class="px-5 py-4 text-right"><Button @click="$emit('manage', user)">Verwalten</Button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import type { AdminUser } from '~/types/admin'

defineProps<{ users: AdminUser[], currentUserId?: string }>()
defineEmits<{ manage: [user: AdminUser] }>()

function displayName(user: AdminUser) {
  return user.display_name || [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(new Date(value)) : 'Noch nie'
}
</script>
