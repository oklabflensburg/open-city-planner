<template>
  <Card class="overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3">
      <h2 class="text-[13px] font-semibold text-[#3f4448]">Spitzenmieten in den Teillagen (€/qm)</h2>
      <Info class="size-4 text-[#9aa0a5]" />
    </div>
    <div v-if="analytics.loading && !analytics.data" class="m-4 h-20 animate-pulse rounded-xl bg-slate-100" />
    <div v-else-if="rows.length" class="overflow-x-auto">
      <table class="w-full min-w-[330px] text-left text-[11px]">
        <thead class="bg-[#e9e9e7] text-[#656b70]">
          <tr>
            <th class="px-4 py-2 font-semibold">Lage</th>
            <th v-for="size in sizes" :key="size" class="px-3 py-2 text-right font-semibold">{{ size }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.location" class="border-t border-[#ececec]">
            <td class="px-4 py-3 text-[#3f4448]">{{ row.location }}</td>
            <td v-for="size in sizeKeys" :key="size" class="px-3 py-3 text-right">{{ row[size] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="analytics.data?.prime_rents.period" class="px-4 py-3 text-[10px] text-slate-500">Stand: {{ analytics.data.prime_rents.period }}</p>
    </div>
    <p v-else class="mx-4 mb-4 rounded-xl bg-slate-50 px-3 py-5 text-center text-xs leading-5 text-slate-600">Für die aktuelle Auswahl liegen keine öffentlichen Mietdaten vor.</p>
  </Card>
</template>

<script setup lang="ts">
import { Info } from '@lucide/vue'

const sizes = ['S', 'M', 'L', 'XL']
const sizeKeys = ['s', 'm', 'l', 'xl'] as const
const analytics = useAnalyticsStore()
const rows = computed(() => analytics.data?.prime_rents.rows || [])
</script>
