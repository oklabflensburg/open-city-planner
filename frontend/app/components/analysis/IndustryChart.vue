<template>
  <Card class="p-4">
    <div class="mb-3 flex items-start justify-between gap-3">
      <div>
        <h2 class="text-[13px] font-semibold text-[#3f4448]">Shops nach Branche</h2>
        <p class="mt-1 text-[10px] leading-snug text-[#5f666d]">Aktuell gefilterte Flächen nach Branche</p>
      </div>
      <Info class="mt-0.5 size-4 shrink-0 text-[#9aa0a5]" />
    </div>
    <div v-if="analytics.loading && !analytics.data" class="mx-auto h-[180px] w-[180px] animate-pulse rounded-full bg-slate-100" />
    <div v-else-if="segments.length" class="flex justify-center">
      <svg class="h-[180px] w-[180px]" viewBox="-1 -1 2 2" role="img" aria-label="Branchenverteilung">
        <path
          v-for="segment in segments"
          :key="segment.key"
          :d="segment.path"
          :fill="segment.color"
          stroke="#ffffff"
          stroke-width="0.012"
          class="cursor-pointer transition-opacity"
          :class="{ 'opacity-45': highlighted && highlighted !== segment.key }"
          @mouseenter="mapStore.categoryHighlight = segment.key"
          @mouseleave="mapStore.categoryHighlight = null"
          @focus="mapStore.categoryHighlight = segment.key"
          @blur="mapStore.categoryHighlight = null"
          tabindex="0"
        >
          <title>{{ segment.label }}: {{ segment.value }}</title>
        </path>
      </svg>
    </div>
    <p v-else class="rounded-xl bg-slate-50 px-3 py-8 text-center text-xs text-slate-600">Für die aktuelle Auswahl liegen keine Daten vor.</p>
    <p v-if="segments.length" class="mt-2 text-center text-[11px] text-slate-500">Gesamt: {{ total.toLocaleString('de-DE') }} Flächen</p>
  </Card>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { industries, industryColors } from '~/utils/industries'

const mapStore = useMapStore()
const analytics = useAnalyticsStore()
const highlighted = computed(() => mapStore.categoryHighlight)

const polar = (angle: number) => [Math.cos(angle), Math.sin(angle)]
const segmentPath = (start: number, end: number) => {
  const [sx, sy] = polar(start)
  const [ex, ey] = polar(end)
  const largeArc = end - start > Math.PI ? 1 : 0
  return `M 0 0 L ${sx} ${sy} A 1 1 0 ${largeArc} 1 ${ex} ${ey} Z`
}

const segments = computed(() => {
  const counts = new Map((analytics.data?.industry_distribution || []).map(item => [item.category, item.count]))
  const available = industries.map(industry => ({ ...industry, value: counts.get(industry.key) || 0 })).filter(industry => industry.value > 0)
  const sum = available.reduce((value, industry) => value + industry.value, 0)
  let angle = -Math.PI / 2
  return available.map((industry) => {
    const span = (industry.value / sum) * Math.PI * 2
    const path = segmentPath(angle, angle + span)
    angle += span
    return {
      key: industry.key,
      label: industry.label,
      value: industry.value,
      color: industryColors[industry.key],
      path
    }
  })
})
const total = computed(() => segments.value.reduce((sum, segment) => sum + segment.value, 0))
</script>
