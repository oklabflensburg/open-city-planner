<template>
  <div>
    <div class="grid gap-4 md:hidden">
      <Card v-for="item in items" :key="item.id" class="p-4">
        <p class="text-sm text-slate-500">{{ formatAuditDate(item.created_at) }}</p>
        <StatusBadge class="mt-3" :tone="auditActionTone(item.action)">{{ auditActionLabel(item.action) }}</StatusBadge>
        <p class="mt-3 break-words font-bold text-slate-950">{{ item.resource.label }}</p>
        <p class="mt-2 break-words text-sm leading-6 text-slate-600">{{ item.summary }}</p>
        <dl class="mt-3 text-sm"><dt class="font-semibold text-slate-500">Ausgeführt von</dt><dd class="mt-1 break-all text-slate-800">{{ actorLabel(item) }}</dd></dl>
        <Button class="mt-4 min-h-11 w-full" @click="$emit('select', item)">Details ansehen</Button>
      </Card>
    </div>

    <Card class="hidden overflow-hidden md:block">
      <div class="overflow-x-auto">
        <table class="w-full min-w-[960px] text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
            <tr><th scope="col" class="px-5 py-4">Zeitpunkt</th><th scope="col" class="px-5 py-4">Benutzer</th><th scope="col" class="px-5 py-4">Aktion</th><th scope="col" class="px-5 py-4">Objekt</th><th scope="col" class="px-5 py-4">Zusammenfassung</th><th scope="col" class="px-5 py-4"><span class="sr-only">Details</span></th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in items" :key="item.id" class="align-top hover:bg-slate-50/70">
              <td class="w-44 px-5 py-4 text-slate-600">{{ formatAuditDate(item.created_at) }}</td>
              <td class="max-w-56 break-words px-5 py-4"><span class="font-semibold text-slate-900">{{ item.actor?.display_name || (item.actor ? item.actor.email : 'System') }}</span><span v-if="item.actor" class="mt-1 block break-all text-xs text-slate-500">{{ item.actor.email }}</span></td>
              <td class="px-5 py-4"><StatusBadge :tone="auditActionTone(item.action)">{{ auditActionLabel(item.action) }}</StatusBadge></td>
              <td class="max-w-52 break-words px-5 py-4"><span class="font-semibold">{{ item.resource.label }}</span><span class="mt-1 block text-xs text-slate-500">{{ item.resource.type }}</span></td>
              <td class="max-w-md break-words px-5 py-4 leading-6 text-slate-600">{{ item.summary }}</td>
              <td class="px-5 py-4 text-right"><Button @click="$emit('select', item)">Details</Button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import type { AuditLogItem } from '~/types/admin'
import { auditActionLabel, auditActionTone, formatAuditDate } from '~/utils/auditLog'

defineProps<{ items: AuditLogItem[] }>()
defineEmits<{ select: [item: AuditLogItem] }>()
const actorLabel = (item: AuditLogItem) => item.actor ? `${item.actor.display_name || item.actor.email} · ${item.actor.email}` : 'System'
</script>
