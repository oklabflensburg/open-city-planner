<template>
  <article class="group flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
    <a
      :href="project.websiteUrl || project.codeForGermanyUrl"
      target="_blank"
      rel="noopener noreferrer"
      class="block overflow-hidden bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#154d73]"
      :aria-label="`${project.title} in neuem Fenster öffnen`"
    >
      <img
        v-if="project.thumbnail"
        :src="project.thumbnail"
        :alt="`Vorschau des Projekts ${project.title}`"
        width="1200"
        height="675"
        loading="lazy"
        decoding="async"
        class="aspect-video w-full object-contain transition duration-300 group-hover:scale-[1.015]"
      >
      <div v-else class="flex aspect-video items-center justify-center bg-gradient-to-br from-sky-50 to-slate-100 text-[#154d73]">
        <Map class="size-10" aria-hidden="true" />
        <span class="sr-only">Keine Vorschau verfügbar</span>
      </div>
    </a>

    <div class="flex flex-1 flex-col p-5">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-bold uppercase tracking-wide text-[#154d73]">{{ project.category }}</span>
        <StatusBadge :tone="status.tone">{{ status.label }}</StatusBadge>
      </div>
      <h2 class="mt-3 text-lg font-bold leading-snug text-slate-950">{{ project.title }}</h2>
      <p class="mt-3 flex-1 text-sm leading-6 text-slate-600">{{ project.description }}</p>

      <a
        :href="project.websiteUrl || project.codeForGermanyUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="page-button-primary mt-5 w-full"
        :aria-label="`${project.title} in neuem Fenster öffnen`"
      >
        Projekt öffnen
        <ExternalLink class="size-4" aria-hidden="true" />
      </a>

      <ul class="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-slate-100 pt-4 text-sm font-semibold text-slate-600" aria-label="Projektlinks">
        <li v-if="project.websiteUrl">
          <a :href="project.websiteUrl" target="_blank" rel="noopener noreferrer" class="inline-flex min-h-11 items-center gap-1.5 hover:text-[#154d73]">
            <Globe2 class="size-4" aria-hidden="true" /> Website
          </a>
        </li>
        <li v-if="project.githubUrl">
          <a :href="project.githubUrl" target="_blank" rel="noopener noreferrer" :aria-label="`Quellcode von ${project.title} in neuem Fenster öffnen`" class="inline-flex min-h-11 items-center gap-1.5 hover:text-[#154d73]">
            <ProviderIcon provider="github" class="size-4" /> GitHub
          </a>
        </li>
        <li v-if="project.dataSourceUrl">
          <a :href="project.dataSourceUrl" target="_blank" rel="noopener noreferrer" :aria-label="`Datenquelle von ${project.title} in neuem Fenster öffnen`" class="inline-flex min-h-11 items-center gap-1.5 hover:text-[#154d73]">
            <Database class="size-4" aria-hidden="true" /> Datenquelle
          </a>
        </li>
        <li>
          <a :href="project.codeForGermanyUrl" target="_blank" rel="noopener noreferrer" :aria-label="`Details zu ${project.title} bei Code for Germany in neuem Fenster öffnen`" class="inline-flex min-h-11 items-center gap-1.5 hover:text-[#154d73]">
            <Info class="size-4" aria-hidden="true" /> Details
          </a>
        </li>
      </ul>
    </div>
  </article>
</template>

<script setup lang="ts">
import { Database, ExternalLink, Globe2, Info, Map } from 'lucide-vue-next'
import { okLabProjectStatus, type OKLabProject } from '~/config/okLabProjects'

const props = defineProps<{ project: OKLabProject }>()
const status = computed(() => okLabProjectStatus[props.project.status])
</script>
