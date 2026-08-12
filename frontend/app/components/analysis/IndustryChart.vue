<template>
  <Card class="p-4">
    <div class="mb-3 flex items-start justify-between gap-3">
      <div>
        <h2 class="text-[13px] font-semibold text-[#3f4448]">Shops nach Branche</h2>
        <p class="mt-1 text-[10px] leading-snug text-[#5f666d]">
          Klicken Sie auf die Warengruppe im Diagramm, um die genaue Aufteilung bzw. eine Hervorhebung auf der Karte zu erhalten.
        </p>
      </div>
      <Info class="mt-0.5 size-4 shrink-0 text-[#9aa0a5]" />
    </div>
    <div class="flex justify-center">
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
  </Card>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { industries, industryColors } from '~/utils/industries'

const mapStore = useMapStore()
const highlighted = computed(() => mapStore.categoryHighlight)

const polar = (angle: number) => [Math.cos(angle), Math.sin(angle)]
const segmentPath = (start: number, end: number) => {
  const [sx, sy] = polar(start)
  const [ex, ey] = polar(end)
  const largeArc = end - start > Math.PI ? 1 : 0
  return `M 0 0 L ${sx} ${sy} A 1 1 0 ${largeArc} 1 ${ex} ${ey} Z`
}

const segments = computed(() => {
  const total = industries.reduce((sum, industry) => sum + industry.value, 0)
  let angle = -Math.PI / 2
  return industries.map((industry) => {
    const span = (industry.value / total) * Math.PI * 2
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
</script>

