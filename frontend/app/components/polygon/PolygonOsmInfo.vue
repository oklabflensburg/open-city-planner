<template>
  <section :class="compact ? '' : 'rounded-xl border border-[#dfe4e6] bg-white p-6'" aria-labelledby="osm-information">
    <div class="flex items-center justify-between gap-3">
      <h2 id="osm-information" :class="compact ? 'text-xs font-bold uppercase tracking-wide text-slate-500' : 'text-lg font-bold text-[#202427]'">OpenStreetMap-Daten</h2>
      <span v-if="info?.matches.length" class="text-xs text-[#687176]">{{ info.matches.length }} {{ info.matches.length === 1 ? 'Objekt' : 'Objekte' }}</span>
    </div>

    <div v-if="loading" class="mt-3 space-y-2" role="status" aria-label="OpenStreetMap-Daten werden geladen">
      <div class="h-3 w-3/4 animate-pulse rounded bg-slate-200" />
      <div class="h-3 w-1/2 animate-pulse rounded bg-slate-200" />
    </div>
    <div v-else-if="error" class="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
      <p>OpenStreetMap-Daten konnten momentan nicht geladen werden.</p>
      <button type="button" class="mt-2 font-bold text-[#154d73] underline" @click="$emit('retry')">Erneut versuchen</button>
    </div>
    <p v-else-if="!info?.primary_match" class="mt-3 text-sm leading-6 text-[#687176]">
      Für diese Fläche wurden keine passenden OpenStreetMap-Daten gefunden.
    </p>
    <template v-else>
      <OsmObjectCard :object="info.primary_match" :compact="compact" primary />
      <details v-if="!compact && info.matches.length > 1" class="mt-4 border-t border-[#e5e9eb] pt-4">
        <summary class="cursor-pointer text-sm font-bold text-[#154d73]">Weitere Treffer ({{ info.matches.length - 1 }})</summary>
        <div class="mt-3 space-y-3">
          <OsmObjectCard v-for="object in info.matches.slice(1)" :key="`${object.osm_type}-${object.osm_id}`" :object="object" />
        </div>
      </details>
    </template>
    <div v-if="!compact && info?.primary_match" class="mt-4 border-t border-slate-200 pt-4">
      <p class="mb-2 text-xs leading-5 text-slate-600">Die Daten stammen aus OpenStreetMap und können dort von der Community ergänzt und aktualisiert werden.</p>
      <OsmContributeAction
        :latitude="info.primary_match.centroid?.latitude"
        :longitude="info.primary_match.centroid?.longitude"
        :zoom="info.primary_match.osm_type === 'node' ? 19 : 18"
        :vacant="info.primary_match.occupancy_status === 'VACANT'"
      />
    </div>
    <p v-if="!compact" class="mt-4 text-xs text-[#687176]">
      Quelle: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 font-semibold text-[#154d73] underline" aria-label="Urheberrechts- und Lizenzhinweise bei OpenStreetMap öffnen"><ProviderIcon provider="openstreetmap" class="size-4" /> OpenStreetMap-Mitwirkende</a> · Die Angaben bleiben eine schreibgeschützte Referenz; Stadtplaner bearbeitet ausschließlich seine eigene Datenebene.
    </p>
  </section>
</template>

<script setup lang="ts">
import type { PolygonOsmInfo } from '~/types/osm'

defineProps<{ info: PolygonOsmInfo | null, loading: boolean, error: string | null, compact?: boolean }>()
defineEmits<{ retry: [] }>()
</script>
