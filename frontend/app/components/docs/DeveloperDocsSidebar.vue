<template>
  <nav aria-label="Entwicklerdokumentation" class="space-y-6">
    <div v-for="group in groups" :key="group.label">
      <h2 class="mb-2 text-xs font-black uppercase tracking-[0.14em] text-slate-500">{{ group.label }}</h2>
      <ul class="space-y-1">
        <li v-for="item in group.pages" :key="item.slug">
          <NuxtLink
            :to="pathFor(item.slug)"
            class="block rounded-lg px-3 py-2 text-sm font-semibold transition-colors"
            :class="item.slug === activeSlug ? 'bg-[#e8f1f6] text-[#154d73]' : 'text-slate-700 hover:bg-slate-100 hover:text-slate-950'"
            @click="$emit('navigate')"
          >
            {{ item.navTitle }}
          </NuxtLink>
        </li>
      </ul>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { developerDocumentationPages } from '~/config/developerDocumentation'

const props = defineProps<{ activeSlug: string }>()
defineEmits<{ navigate: [] }>()

const groups = computed(() => {
  const values = new Map<string, typeof developerDocumentationPages>()
  for (const page of developerDocumentationPages) {
    const pages = values.get(page.group) || []
    pages.push(page)
    values.set(page.group, pages)
  }
  return Array.from(values, ([label, pages]) => ({ label, pages }))
})

function pathFor(slug: string) {
  return slug ? `/dokumentation/entwickler/${slug}` : '/dokumentation/entwickler'
}
</script>
