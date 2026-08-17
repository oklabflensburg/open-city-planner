<template>
  <nav
    v-if="links.wikipedia || links.wikidata"
    :class="variant === 'card' ? 'grid gap-4 sm:grid-cols-2' : 'flex flex-wrap gap-x-4 gap-y-2 text-sm'"
    :aria-label="`Externe Quellen zu ${areaName}`"
  >
    <ExternalSourceLink
      v-if="links.wikipedia"
      label="Wikipedia"
      :title="links.wikipedia.title"
      :url="links.wikipedia.url"
      description="Enzyklopädischer Artikel"
      :accessible-name="`${links.wikipedia.title} bei Wikipedia öffnen`"
      :variant="variant"
    />
    <ExternalSourceLink
      v-if="links.wikidata"
      label="Wikidata"
      :title="links.wikidata.id"
      :url="links.wikidata.url"
      description="Strukturierte offene Wissensdaten"
      :accessible-name="`${areaName} bei Wikidata öffnen`"
      :variant="variant"
    />
  </nav>
</template>

<script setup lang="ts">
import type { AnalysisArea } from '~/types/analysisArea'

withDefaults(defineProps<{
  areaName: string
  links: AnalysisArea['external_links']
  variant?: 'compact' | 'card'
}>(), { variant: 'compact' })
</script>
