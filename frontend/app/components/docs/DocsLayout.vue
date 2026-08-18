<template>
  <div class="min-h-screen bg-white">
    <a href="#docs-content" class="sr-only z-[100] rounded bg-white px-4 py-3 font-bold text-[#154d73] focus:not-sr-only focus:fixed focus:left-4 focus:top-20">Zum Dokumentationsinhalt springen</a>
    <div class="border-b border-slate-200 bg-slate-50/80">
      <div class="mx-auto max-w-[1536px] px-4 py-6 sm:px-6 lg:px-8">
        <DocsSearch />
      </div>
    </div>

    <div class="mx-auto max-w-[1536px] px-4 py-8 sm:px-6 lg:px-8">
      <div class="mb-6 flex gap-3 xl:hidden">
        <button class="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-slate-800 hover:bg-slate-50" type="button" aria-controls="docs-mobile-navigation" :aria-expanded="mobileNavigationOpen" @click="mobileNavigationOpen = !mobileNavigationOpen">
          <Menu class="size-4" aria-hidden="true" /> Inhalte
        </button>
        <button class="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-slate-800 hover:bg-slate-50 lg:hidden" type="button" aria-controls="docs-mobile-toc" :aria-expanded="mobileTocOpen" @click="mobileTocOpen = !mobileTocOpen">
          <List class="size-4" aria-hidden="true" /> Auf dieser Seite
        </button>
      </div>
      <div v-if="mobileNavigationOpen" id="docs-mobile-navigation" class="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4 xl:hidden">
        <DocsSidebar :active-slug="page.slug" @navigate="mobileNavigationOpen = false" />
      </div>
      <div v-if="mobileTocOpen" id="docs-mobile-toc" class="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4 lg:hidden">
        <DocsTableOfContents :sections="page.sections" />
      </div>

      <div class="grid gap-10 xl:grid-cols-[240px_minmax(0,1fr)_220px]">
        <aside class="hidden xl:block">
          <div class="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pr-2"><DocsSidebar :active-slug="page.slug" /></div>
        </aside>

        <article id="docs-content" class="min-w-0 max-w-4xl">
          <PageHeader :title="page.title" :description="page.description" :breadcrumbs="breadcrumbs" class="mb-10">
            <template #badge><DocsRoleBadge :audience="page.audience" /></template>
          </PageHeader>

          <DocsContent :page="page" />

          <nav class="mt-10 grid gap-3 border-t border-slate-200 pt-8 sm:grid-cols-2" aria-label="Weitere Dokumentationsseiten">
            <NuxtLink v-if="previous" :to="documentationPath(previous)" class="rounded-xl border border-slate-200 p-4 hover:border-[#4f86a8] hover:bg-slate-50">
              <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Zurück</span><span class="mt-1 flex items-center gap-2 font-bold text-[#154d73]"><ArrowLeft class="size-4" />{{ previous.navTitle }}</span>
            </NuxtLink><span v-else />
            <NuxtLink v-if="next" :to="documentationPath(next)" class="rounded-xl border border-slate-200 p-4 text-right hover:border-[#4f86a8] hover:bg-slate-50">
              <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Weiter</span><span class="mt-1 flex items-center justify-end gap-2 font-bold text-[#154d73]">{{ next.navTitle }}<ArrowRight class="size-4" /></span>
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
import { ArrowLeft, ArrowRight, List, Menu } from 'lucide-vue-next'
import type { DocumentationPage } from '~/types/documentation'
import { documentationPath, getDocumentationNeighbors } from '~/utils/documentation'

const props = defineProps<{ page: DocumentationPage }>()
const mobileNavigationOpen = ref(false)
const mobileTocOpen = ref(false)
const neighbors = computed(() => getDocumentationNeighbors(props.page))
const previous = computed(() => neighbors.value.previous)
const next = computed(() => neighbors.value.next)
const breadcrumbs = computed(() => [
  { label: 'Startseite', to: '/' },
  ...(props.page.slug ? [{ label: 'Dokumentation', to: '/dokumentation' }, { label: props.page.group }, { label: props.page.title }] : [{ label: 'Dokumentation' }])
])

watch(() => props.page.slug, () => {
  mobileNavigationOpen.value = false
  mobileTocOpen.value = false
})
</script>
