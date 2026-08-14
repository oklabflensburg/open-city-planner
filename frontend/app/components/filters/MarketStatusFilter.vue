<template>
  <div class="space-y-5">
    <fieldset>
      <legend class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</legend>
      <div class="grid gap-1">
        <button v-for="item in occupancyOptions" :key="item.value" class="filter-choice" type="button" :aria-pressed="filter.occupancyStatuses.includes(item.value)" @click="filter.toggleOccupancy(item.value)">
          <span class="size-3 rounded-full" :class="item.color" aria-hidden="true" />
          {{ item.label }}
        </button>
      </div>
    </fieldset>
    <fieldset>
      <legend class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Betriebsform</legend>
      <div class="grid gap-1">
        <button v-for="item in structureOptions" :key="item.value" class="filter-choice" type="button" :aria-pressed="filter.businessStructures.includes(item.value)" @click="filter.toggleBusinessStructure(item.value)">
          {{ item.label }}
        </button>
      </div>
    </fieldset>
  </div>
</template>

<script setup lang="ts">
import type { BusinessStructure, OccupancyStatus } from '~/types/geo'

const filter = useFilterStore()
const occupancyOptions: Array<{ value: OccupancyStatus, label: string, color: string }> = [
  { value: 'OCCUPIED', label: 'Belegt', color: 'bg-emerald-500' },
  { value: 'VACANT', label: 'Leerstehend', color: 'bg-rose-500' },
  { value: 'UNKNOWN', label: 'Unbekannt', color: 'bg-slate-400' }
]
const structureOptions: Array<{ value: BusinessStructure, label: string }> = [
  { value: 'CHAIN', label: 'Filialist' },
  { value: 'INDEPENDENT', label: 'Inhabergeführt' },
  { value: 'UNKNOWN', label: 'Unbekannt' }
]
</script>

<style scoped>
.filter-choice {
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.625rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  padding: 0.5rem 0.625rem;
  color: #475569;
  font-size: 0.75rem;
  text-align: left;
}
.filter-choice:hover { background: #f8fafc; }
.filter-choice[aria-pressed="true"] { border-color: #8baabd; background: #edf4f8; color: #154d73; font-weight: 700; }
.filter-choice:focus-visible { outline: 2px solid #154d73; outline-offset: 2px; }
</style>
