<template>
  <AppModal :open="Boolean(item)" title="Audit-Ereignis" description="Unveränderlicher Eintrag aus dem administrativen Auditlog." size="lg" @update:open="value => { if (!value) $emit('close') }">
    <template v-if="item">
      <dl class="grid gap-5 text-sm sm:grid-cols-2">
        <div><dt class="font-semibold text-slate-500">Zeitpunkt</dt><dd class="mt-1 text-slate-950">{{ formatAuditDate(item.created_at) }}</dd></div>
        <div><dt class="font-semibold text-slate-500">Aktion</dt><dd class="mt-1"><StatusBadge :tone="auditActionTone(item.action)">{{ item.action }}</StatusBadge></dd></div>
        <div><dt class="font-semibold text-slate-500">Ausgeführt von</dt><dd class="mt-1 break-all text-slate-950">{{ item.actor?.display_name || (item.actor ? item.actor.email : 'System') }}<span v-if="item.actor" class="block text-slate-500">{{ item.actor.email }}</span></dd></div>
        <div><dt class="font-semibold text-slate-500">Ressource</dt><dd class="mt-1 break-words text-slate-950">{{ item.resource.label }}<span class="block break-all text-slate-500">{{ item.resource.type }}<template v-if="item.resource.id"> · {{ item.resource.id }}</template></span></dd></div>
      </dl>
      <section class="mt-6 border-t border-slate-200 pt-6" aria-labelledby="audit-summary"><h3 id="audit-summary" class="font-bold text-slate-950">Zusammenfassung</h3><p class="mt-2 leading-7 text-slate-700">{{ item.summary }}</p></section>
      <section v-if="changes.length" class="mt-6" aria-labelledby="audit-changes"><h3 id="audit-changes" class="font-bold text-slate-950">Änderungen</h3><div class="mt-3 overflow-x-auto rounded-xl border border-slate-200"><table class="min-w-full text-left text-sm"><thead class="bg-slate-50"><tr><th scope="col" class="px-4 py-3">Feld</th><th scope="col" class="px-4 py-3">Vorher</th><th scope="col" class="px-4 py-3">Nachher</th></tr></thead><tbody class="divide-y divide-slate-200"><tr v-for="change in changes" :key="change.field"><th scope="row" class="px-4 py-3 font-semibold">{{ change.field }}</th><td class="break-words px-4 py-3">{{ displayAuditValue(change.before) }}</td><td class="break-words px-4 py-3">{{ displayAuditValue(change.after) }}</td></tr></tbody></table></div></section>
      <details v-if="Object.keys(item.details).length" class="mt-6 rounded-xl border border-slate-200 p-4"><summary class="cursor-pointer font-bold text-[#154d73]">Technische Details</summary><pre class="mt-4 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ JSON.stringify(item.details, null, 2) }}</pre></details>
      <p v-else class="mt-6 text-sm text-slate-500">Für dieses Ereignis sind keine weiteren Details gespeichert.</p>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import type { AuditLogItem } from '~/types/admin'
import { auditActionTone, auditChangeRows, displayAuditValue, formatAuditDate } from '~/utils/auditLog'

const props = defineProps<{ item: AuditLogItem | null }>()
defineEmits<{ close: [] }>()
const changes = computed(() => props.item ? auditChangeRows(props.item.details) : [])
</script>
