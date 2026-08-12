<template>
  <Card class="p-4">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="text-[13px] font-semibold text-[#3f4448]">Fast Facts</h2>
      <Info class="size-4 text-[#9aa0a5]" aria-hidden="true" />
    </div>
    <div class="grid grid-cols-3 gap-4">
      <div v-for="fact in topFacts" :key="fact.label" class="text-center">
        <component :is="fact.icon" class="mx-auto mb-1 size-4 text-[#2f3337]" />
        <div class="text-[10px] text-[#60666b]">{{ fact.label }}</div>
        <div class="mt-1 rounded-md bg-[#f5f5f5] py-2 text-xl font-light text-[#53585d]">{{ fact.value }}</div>
      </div>
    </div>
    <div class="mt-4 grid grid-cols-2 gap-6">
      <div v-for="fact in bottomFacts" :key="fact.label" class="text-center">
        <component :is="fact.icon" class="mx-auto mb-1 size-4 text-[#2f3337]" />
        <div class="text-[10px] text-[#60666b]">{{ fact.label }}</div>
        <div class="mt-1 rounded-md bg-[#f5f5f5] py-2 text-xl font-light text-[#53585d]">{{ fact.value }}</div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { Building2, Info, Landmark, Network, Store, WalletCards } from 'lucide-vue-next'

const polygonStore = usePolygonStore()

const selectedMetrics = computed(() => polygonStore.selectedMetrics)

const topFacts = computed(() =>
  selectedMetrics.value
    ? [
        { label: 'Fläche', value: `${Math.round(selectedMetrics.value.area_m2).toLocaleString('de-DE')}`, icon: Store },
        { label: 'Umfang', value: `${Math.round(selectedMetrics.value.perimeter_m).toLocaleString('de-DE')}`, icon: Landmark },
        { label: 'Vertices', value: polygonStore.selectedPolygon?.geometry.coordinates[0]?.length || 0, icon: Network }
      ]
    : [
        { label: 'Shops', value: 96, icon: Store },
        { label: 'Leerstand', value: '6%', icon: Landmark },
        { label: 'Filialisierung', value: '71%', icon: Network }
      ]
)

const bottomFacts = computed(() =>
  selectedMetrics.value
    ? [
        { label: 'Zentroid Lng', value: selectedMetrics.value.centroid[0].toFixed(4), icon: Building2 },
        { label: 'Zentroid Lat', value: selectedMetrics.value.centroid[1].toFixed(4), icon: WalletCards }
      ]
    : [
        { label: 'Zentralität', value: 154, icon: Building2 },
        { label: 'Kaufkraft', value: 85, icon: WalletCards }
      ]
)
</script>

