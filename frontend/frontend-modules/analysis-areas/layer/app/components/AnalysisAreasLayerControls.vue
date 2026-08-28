<template>
  <div class="grid gap-1" aria-label="Administrative Gebietsgrenzen">
    <p class="pb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Gebietsgrenzen</p>
    <GisFilterToggleRow
      v-for="item in areaLayers"
      :key="item.type"
      v-model="areas.visibility[item.type]"
      :label="item.label"
      :aria-label="`${item.label} anzeigen`"
      :active-color="item.activeColor"
    />
  </div>
</template>

<script setup lang="ts">
import { useAnalysisAreasStore } from '../stores/analysisAreas'

const areas = useAnalysisAreasStore()
const areaLayers = [
  { type: 'MUNICIPALITY' as const, label: 'Gemeinde', activeColor: '#1d4ed8' },
  { type: 'DISTRICT' as const, label: 'Stadtteile', activeColor: '#15803d' },
  { type: 'QUARTER' as const, label: 'Quartiere', activeColor: '#b45309' }
]
</script>
