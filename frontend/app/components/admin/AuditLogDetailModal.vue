<template>
  <AppModal :open="Boolean(item)" title="Audit-Ereignis" description="Unveränderlicher Eintrag aus dem administrativen Auditlog." size="lg" @update:open="value => { if (!value) $emit('close') }">
    <template v-if="item">
      <div class="min-w-0 max-w-full">
      <dl class="grid min-w-0 gap-5 text-sm sm:grid-cols-2">
        <div class="min-w-0"><dt class="font-semibold text-slate-500">Zeitpunkt</dt><dd class="mt-1 text-slate-950 [overflow-wrap:anywhere]">{{ formatAuditDate(item.created_at) }}</dd></div>
        <div class="min-w-0"><dt class="font-semibold text-slate-500">Aktion</dt><dd class="mt-1 min-w-0"><StatusBadge class="max-w-full whitespace-normal text-left [overflow-wrap:anywhere]" :tone="auditActionTone(item.action)">{{ auditActionLabel(item.action) }}</StatusBadge><span class="mt-1 block text-xs text-slate-500 [overflow-wrap:anywhere]">{{ item.action }}</span></dd></div>
        <div class="min-w-0"><dt class="font-semibold text-slate-500">Ausgeführt von</dt><dd class="mt-1 min-w-0 text-slate-950 [overflow-wrap:anywhere]">{{ item.actor?.display_name || (item.actor ? item.actor.email : 'System') }}<span v-if="item.actor" class="block text-slate-500 [overflow-wrap:anywhere]">{{ item.actor.email }}</span></dd></div>
        <div class="min-w-0"><dt class="font-semibold text-slate-500">Ressource</dt><dd class="mt-1 min-w-0 text-slate-950 [overflow-wrap:anywhere]">{{ item.resource.label }}<span class="block text-slate-500 [overflow-wrap:anywhere]">{{ item.resource.type }}<template v-if="item.resource.id"> · {{ item.resource.id }}</template></span></dd></div>
      </dl>
      <section class="mt-6 min-w-0 border-t border-slate-200 pt-6" aria-labelledby="audit-summary"><h3 id="audit-summary" class="font-bold text-slate-950">Zusammenfassung</h3><p class="mt-2 leading-7 text-slate-700 [overflow-wrap:anywhere]">{{ item.summary }}</p></section>
      <section v-if="changes.length" class="mt-6 min-w-0" aria-labelledby="audit-changes">
        <h3 id="audit-changes" class="font-bold text-slate-950">Änderungen</h3>
        <dl class="mt-3 grid min-w-0 gap-3 sm:hidden">
          <div v-for="change in changes" :key="change.field" class="min-w-0 rounded-xl border border-slate-200 p-4 text-sm">
            <dt class="font-bold text-slate-950 [overflow-wrap:anywhere]">{{ change.field }}</dt>
            <dd class="mt-3 min-w-0"><span class="block text-xs font-semibold uppercase tracking-wide text-slate-500">Vorher</span><span class="mt-1 block [overflow-wrap:anywhere]">{{ displayAuditValue(change.before) }}</span></dd>
            <dd class="mt-3 min-w-0"><span class="block text-xs font-semibold uppercase tracking-wide text-slate-500">Nachher</span><span class="mt-1 block [overflow-wrap:anywhere]">{{ displayAuditValue(change.after) }}</span></dd>
          </div>
        </dl>
        <div class="mt-3 hidden min-w-0 max-w-full overflow-hidden rounded-xl border border-slate-200 sm:block"><table class="w-full table-fixed text-left text-sm"><thead class="bg-slate-50"><tr><th scope="col" class="w-1/4 px-4 py-3">Feld</th><th scope="col" class="w-[37.5%] px-4 py-3">Vorher</th><th scope="col" class="w-[37.5%] px-4 py-3">Nachher</th></tr></thead><tbody class="divide-y divide-slate-200"><tr v-for="change in changes" :key="change.field"><th scope="row" class="px-4 py-3 font-semibold [overflow-wrap:anywhere]">{{ change.field }}</th><td class="px-4 py-3 [overflow-wrap:anywhere]">{{ displayAuditValue(change.before) }}</td><td class="px-4 py-3 [overflow-wrap:anywhere]">{{ displayAuditValue(change.after) }}</td></tr></tbody></table></div>
      </section>
      <details v-if="Object.keys(item.details).length" class="mt-6 min-w-0 max-w-full overflow-hidden rounded-xl border border-slate-200 p-4"><summary class="cursor-pointer font-bold text-[#154d73]">Technische Details</summary><pre class="mt-4 max-w-full overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ JSON.stringify(item.details, null, 2) }}</pre></details>
      <p v-else class="mt-6 text-sm text-slate-500">Für dieses Ereignis sind keine weiteren Details gespeichert.</p>
      </div>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import type { AuditLogItem } from '~/types/admin'
import { auditActionLabel, auditActionTone, auditChangeRows, displayAuditValue, formatAuditDate } from '~/utils/auditLog'

const props = defineProps<{ item: AuditLogItem | null }>()
defineEmits<{ close: [] }>()
const changes = computed(() => props.item ? auditChangeRows(props.item.details) : [])
</script>
