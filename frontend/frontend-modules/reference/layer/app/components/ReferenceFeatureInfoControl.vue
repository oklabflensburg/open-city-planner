<template>
  <div class="w-64 rounded-xl border border-violet-200 bg-white p-3 text-left shadow-lg">
    <p class="text-xs font-bold uppercase tracking-wide text-violet-700">Referenzmarker</p>
    <p v-if="info" class="mt-1 font-bold text-slate-900">{{ info.title }}</p>
    <p v-if="info" class="mt-1 text-xs leading-5 text-slate-600">{{ info.description }}</p>
    <p v-else-if="loadError" class="mt-1 text-xs leading-5 text-rose-700" role="alert">Marker konnten nicht geladen werden.</p>
    <p v-else class="mt-1 text-xs leading-5 text-slate-600">Marker auf der Karte auswählen.</p>
  </div>
</template>

<script setup lang="ts">
import type { MapContext } from '#frontend-module-sdk'
import { useMapContext } from '#frontend-module-sdk'
import { onBeforeUnmount, watch } from 'vue'
import {
  createReferenceFeatureInfoProvider,
  referenceSelectionFrom,
  type ReferenceFeatureInfo
} from '../composables/useReferenceFeatureInfo'
import { referenceApiUrl } from '../composables/referenceApi'

const mapContext = useMapContext()
const info = ref<ReferenceFeatureInfo | null>(null)
const loadError = ref(false)
let unregisterProvider: (() => void) | undefined
let unregisterInteraction: (() => void) | undefined

const provider = createReferenceFeatureInfoProvider()

async function loadFeatures(context: MapContext) {
  const config = useRuntimeConfig()
  try {
    const collection = await $fetch<GeoJSON.FeatureCollection>(
      referenceApiUrl(String(config.public.apiBaseUrl), '.geojson')
    )
    const source = context.unsafeMapLibre().getSource('reference.items')
    if (source && 'setData' in source && typeof source.setData === 'function') {
      source.setData(collection)
    }
  } catch {
    loadError.value = true
  }
}

function register(context: MapContext) {
  unregisterProvider = context.featureInfo.register(provider)
  unregisterInteraction = context.interactions.register({
    id: 'reference.items-click',
    moduleId: 'reference',
    event: 'click',
    layerIds: ['reference.items'],
    handler: async (event, activeContext) => {
      const selection = referenceSelectionFrom(event)
      if (!selection) return
      await activeContext.selection.select(selection)
      info.value = await provider.resolveFeatureInfo(selection, activeContext)
      return { handled: true }
    }
  })
  void loadFeatures(context)
}

watch(mapContext, (context) => {
  unregisterInteraction?.()
  unregisterProvider?.()
  unregisterInteraction = undefined
  unregisterProvider = undefined
  if (context) register(context)
}, { immediate: true })

onBeforeUnmount(() => {
  unregisterInteraction?.()
  unregisterProvider?.()
})
</script>
