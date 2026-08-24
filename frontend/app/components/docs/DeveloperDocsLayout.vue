<template>
  <div class="min-h-screen bg-white">
    <a href="#developer-docs-content" class="sr-only z-[100] rounded bg-white px-4 py-3 font-bold text-[#154d73] focus:not-sr-only focus:fixed focus:left-4 focus:top-20">Zum Entwicklerinhalt springen</a>

    <div class="border-b border-slate-200 bg-slate-50/80">
      <div class="mx-auto max-w-[1536px] px-4 py-6 sm:px-6 lg:px-8">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.16em] text-[#4f86a8]">Open City Planner</p>
            <h1 class="mt-1 text-2xl font-black text-slate-950">Entwicklerdokumentation</h1>
            <p class="mt-1 max-w-3xl text-sm text-slate-600">Architektur, APIs, GIS, Datenimporte, intelligente Suche, Tests und Betrieb.</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <NuxtLink to="/dokumentation" class="inline-flex min-h-10 items-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">Benutzerhandbuch</NuxtLink>
            <a :href="projectConfig.github.url" class="inline-flex min-h-10 items-center rounded-lg bg-[#154d73] px-3 text-sm font-bold text-white hover:bg-[#103d5c]">GitHub Repository</a>
          </div>
        </div>
      </div>
    </div>

    <div class="mx-auto max-w-[1536px] px-4 py-8 sm:px-6 lg:px-8">
      <div class="mb-6 xl:hidden">
        <button class="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-slate-800 hover:bg-slate-50" type="button" :aria-expanded="mobileNavigationOpen" aria-controls="developer-docs-mobile-navigation" @click="mobileNavigationOpen = !mobileNavigationOpen">
          <Menu class="size-4" aria-hidden="true" /> Inhalte
        </button>
      </div>

      <div v-if="mobileNavigationOpen" id="developer-docs-mobile-navigation" class="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4 xl:hidden">
        <DeveloperDocsSidebar :active-slug="page.slug" @navigate="mobileNavigationOpen = false" />
      </div>

      <div class="grid gap-10 xl:grid-cols-[250px_minmax(0,1fr)_220px]">
        <aside class="hidden xl:block">
          <div class="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pr-2">
            <DeveloperDocsSidebar :active-slug="page.slug" />
          </div>
        </aside>

        <article id="developer-docs-content" class="min-w-0 max-w-4xl">
          <PageHeader :title="page.title" :description="page.description" :breadcrumbs="breadcrumbs" class="mb-10">
            <template #badge><StatusBadge tone="info">Für Entwickler</StatusBadge></template>
          </PageHeader>
          <DocsContent :page="page" />

          <nav class="mt-10 grid gap-3 border-t border-slate-200 pt-8 sm:grid-cols-2" aria-label="Weitere Entwicklerseiten">
            <NuxtLink v-if="previous" :to="developerDocumentationPath(previous)" class="rounded-xl border border-slate-200 p-4 hover:border-[#4f86a8] hover:bg-slate-50">
              <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Zurück</span>
              <span class="mt-1 flex items-center gap-2 font-bold text-[#154d73]"><ArrowLeft class="size-4" />{{ previous.navTitle }}</span>
            </NuxtLink>
            <span v-else />
            <NuxtLink v-if="next" :to="developerDocumentationPath(next)" class="rounded-xl border border-slate-200 p-4 text-right hover:border-[#4f86a8] hover:bg-slate-50">
              <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Weiter</span>
              <span class="mt-1 flex items-center justify-end gap-2 font-bold text-[#154d73]">{{ next.navTitle }}<ArrowRight class="size-4" /></span>
            </NuxtLink>
          </nav>
        </article>

        <aside class="hidden lg:block">
          <div class="sticky top-24"><DocsTableOfContents :sections="page.sections" /></div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, Menu } from '@lucide/vue'
import type { DocumentationPage } from '~/types/documentation'
import { developerDocumentationPages } from '~/config/developerDocumentation'
import { projectConfig } from '~/config/project'

const props = defineProps<{ page: DocumentationPage }>()
const mobileNavigationOpen = ref(false)
const pageIndex = computed(() => developerDocumentationPages.findIndex(candidate => candidate.slug === props.page.slug))
const previous = computed(() => pageIndex.value > 0 ? developerDocumentationPages[pageIndex.value - 1] : undefined)
const next = computed(() => pageIndex.value >= 0 && pageIndex.value < developerDocumentationPages.length - 1 ? developerDocumentationPages[pageIndex.value + 1] : undefined)
const breadcrumbs = computed(() => [
  { label: 'Startseite', to: '/' },
  { label: 'Dokumentation', to: '/dokumentation' },
  ...(props.page.slug ? [{ label: 'Entwickler', to: '/dokumentation/entwickler' }, { label: props.page.title }] : [{ label: 'Entwickler' }])
])

function developerDocumentationPath(page: DocumentationPage) {
  return page.slug ? `/dokumentation/entwickler/${page.slug}` : '/dokumentation/entwickler'
}

watch(() => props.page.slug, () => { mobileNavigationOpen.value = false })
</script>
