<template>
  <div class="min-w-0 max-w-full">
    <ul class="grid min-w-0 gap-4 lg:hidden" aria-label="Audit-Ereignisse">
      <li v-for="item in items" :key="item.id" class="min-w-0">
        <Card class="min-w-0 max-w-full p-4 sm:p-5">
          <div class="flex min-w-0 flex-col items-start gap-3 sm:flex-row sm:justify-between">
            <time class="text-sm text-slate-500" :datetime="item.created_at">{{ formatAuditDate(item.created_at) }}</time>
            <StatusBadge class="max-w-full whitespace-normal text-left [overflow-wrap:anywhere]" :tone="auditActionTone(item.action)">{{ auditActionLabel(item.action) }}</StatusBadge>
          </div>

          <dl class="mt-4 grid min-w-0 gap-4 text-sm sm:grid-cols-2">
            <div class="min-w-0">
              <dt class="font-semibold text-slate-500">Ausgeführt von</dt>
              <dd class="mt-1 min-w-0 text-slate-800">
                <span class="block font-semibold [overflow-wrap:anywhere]">{{ actorName(item) }}</span>
                <span v-if="item.actor" class="mt-1 block text-xs text-slate-500 [overflow-wrap:anywhere]">{{ item.actor.email }}</span>
              </dd>
            </div>
            <div class="min-w-0">
              <dt class="font-semibold text-slate-500">Objekt</dt>
              <dd class="mt-1 min-w-0 text-slate-800">
                <span class="block font-semibold [overflow-wrap:anywhere]">{{ item.resource.label }}</span>
                <span class="mt-1 block text-xs text-slate-500 [overflow-wrap:anywhere]">{{ resourceMeta(item) }}</span>
              </dd>
            </div>
          </dl>

          <div class="mt-4 min-w-0">
            <h3 class="text-sm font-semibold text-slate-500">Zusammenfassung</h3>
            <p class="mt-1 line-clamp-4 [overflow-wrap:anywhere] text-sm leading-6 text-slate-700">{{ item.summary }}</p>
          </div>
          <Button class="mt-4 min-h-11 w-full sm:w-auto" @click="$emit('select', item)">Details ansehen</Button>
        </Card>
      </li>
    </ul>

    <Card class="hidden min-w-0 max-w-full overflow-hidden lg:block">
      <div class="min-w-0 max-w-full">
        <table class="w-full table-fixed text-left text-sm">
          <colgroup>
            <col class="w-[14%]">
            <col class="w-[17%]">
            <col class="w-[17%]">
            <col class="w-[16%]">
            <col class="w-[25%]">
            <col class="w-[11%]">
          </colgroup>
          <thead class="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
            <tr><th scope="col" class="px-3 py-4 xl:px-5">Zeitpunkt</th><th scope="col" class="px-3 py-4 xl:px-5">Benutzer</th><th scope="col" class="px-3 py-4 xl:px-5">Aktion</th><th scope="col" class="px-3 py-4 xl:px-5">Objekt</th><th scope="col" class="px-3 py-4 xl:px-5">Zusammenfassung</th><th scope="col" class="px-3 py-4 xl:px-5"><span class="sr-only">Details</span></th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in items" :key="item.id" class="align-top hover:bg-slate-50/70">
              <td class="min-w-0 px-3 py-4 text-slate-600 xl:px-5"><time class="[overflow-wrap:anywhere]" :datetime="item.created_at">{{ formatAuditDate(item.created_at) }}</time></td>
              <td class="min-w-0 px-3 py-4 xl:px-5"><span class="block font-semibold text-slate-900 [overflow-wrap:anywhere]">{{ actorName(item) }}</span><span v-if="item.actor" class="mt-1 block text-xs text-slate-500 [overflow-wrap:anywhere]">{{ item.actor.email }}</span></td>
              <td class="min-w-0 px-3 py-4 xl:px-5"><StatusBadge class="max-w-full whitespace-normal text-left [overflow-wrap:anywhere]" :tone="auditActionTone(item.action)">{{ auditActionLabel(item.action) }}</StatusBadge></td>
              <td class="min-w-0 px-3 py-4 xl:px-5"><span class="block font-semibold [overflow-wrap:anywhere]">{{ item.resource.label }}</span><span class="mt-1 block text-xs text-slate-500 [overflow-wrap:anywhere]">{{ resourceMeta(item) }}</span></td>
              <td class="min-w-0 px-3 py-4 leading-6 text-slate-600 xl:px-5"><span class="line-clamp-3 [overflow-wrap:anywhere]">{{ item.summary }}</span></td>
              <td class="px-3 py-4 text-right xl:px-5"><Button class="max-w-full px-3" @click="$emit('select', item)">Details</Button></td>
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
const actorName = (item: AuditLogItem) => item.actor?.display_name || item.actor?.email || 'System'
const resourceMeta = (item: AuditLogItem) => [item.resource.type, item.resource.id].filter(Boolean).join(' · ')
</script>
