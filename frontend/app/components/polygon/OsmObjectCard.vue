<template>
  <article :class="compact ? 'mt-3' : 'rounded-lg border border-[#e1e6e8] p-4'">
    <p v-if="primary && !compact" class="text-[11px] font-bold uppercase tracking-wide text-[#687176]">Beste Übereinstimmung</p>
    <h3 v-if="displayName" class="mt-1 font-bold text-[#202427]">{{ displayName }}</h3>
    <dl :class="compact ? 'mt-2 space-y-1 text-xs' : 'mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2'">
      <div><dt class="text-[#687176]">{{ category.label }}</dt><dd class="font-semibold text-[#202427]">{{ category.value }}</dd></div>
      <div v-for="item in localizedDetails" :key="item.label"><dt class="text-[#687176]">{{ item.label }}</dt><dd class="font-semibold text-[#202427]">{{ item.value }}</dd></div>
      <div v-if="object.brand"><dt class="text-[#687176]">Marke</dt><dd class="font-semibold text-[#202427]">{{ object.brand }}</dd></div>
      <div v-if="object.operator"><dt class="text-[#687176]">Betreiber</dt><dd class="font-semibold text-[#202427]">{{ object.operator }}</dd></div>
      <div v-if="object.opening_hours"><dt class="text-[#687176]">Öffnungszeiten</dt><dd class="font-semibold text-[#202427]">{{ object.opening_hours }}</dd></div>
      <div v-if="address"><dt class="text-[#687176]">OpenStreetMap-Adresse</dt><dd class="font-semibold text-[#202427]">{{ address }}</dd></div>
      <div v-if="!compact && object.phone"><dt class="text-[#687176]">Telefon</dt><dd><a class="font-semibold text-[#154d73] underline" :href="`tel:${object.phone}`">{{ object.phone }}</a></dd></div>
      <div v-if="!compact && object.email"><dt class="text-[#687176]">E-Mail</dt><dd><a class="font-semibold text-[#154d73] underline" :href="`mailto:${object.email}`">{{ object.email }}</a></dd></div>
      <div v-if="!compact && object.level"><dt class="text-[#687176]">Ebene</dt><dd class="font-semibold text-[#202427]">{{ object.level }}</dd></div>
      <div v-if="!compact && object.building_levels"><dt class="text-[#687176]">Gebäudeebenen</dt><dd class="font-semibold text-[#202427]">{{ object.building_levels }}</dd></div>
    </dl>
    <AreaExternalLinks
      v-if="object.external_links.wikipedia || object.external_links.wikidata"
      class="mt-3"
      :area-name="displayName || 'OpenStreetMap-Objekt'"
      :links="object.external_links"
    />
    <div class="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs font-bold text-[#154d73]">
      <a v-if="website" :href="website" target="_blank" rel="noopener noreferrer" class="underline">Website</a>
      <a :href="osmObjectUrl(object)" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 underline" aria-label="OpenStreetMap-Objekt öffnen"><ProviderIcon provider="openstreetmap" class="size-4" /> Auf OpenStreetMap ansehen</a>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { OsmObjectInfo } from '~/types/osm'
import { formatOsmAddress, osmObjectTags, osmObjectUrl, safeOsmWebsite } from '~/utils/osm'
import { formatOsmCategory, formatOsmTag, localizedOsmName, osmDetailKeys } from '~/utils/osmTranslations'

const props = defineProps<{ object: OsmObjectInfo, compact?: boolean, primary?: boolean }>()
const tags = computed(() => osmObjectTags(props.object))
const displayName = computed(() => localizedOsmName(tags.value, props.object.name))
const category = computed(() => formatOsmCategory(tags.value))
const localizedDetails = computed(() => osmDetailKeys
  .map(key => formatOsmTag(key, tags.value[key], tags.value))
  .filter((item): item is NonNullable<typeof item> => item !== null))
const address = computed(() => formatOsmAddress(props.object.address))
const website = computed(() => safeOsmWebsite(props.object.website))
</script>
