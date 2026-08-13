<template>
  <nav aria-label="Dokumentationsnavigation">
    <div v-for="group in groups" :key="group.label" class="mb-6">
      <p class="mb-2 px-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{{ group.label }}</p>
      <ul class="space-y-1">
        <li v-for="item in group.pages" :key="item.slug">
          <NuxtLink
            :to="documentationPath(item)"
            class="flex min-h-10 items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="item.slug === activeSlug ? 'bg-[#e8f1f6] text-[#123f5f]' : ''"
            :aria-current="item.slug === activeSlug ? 'page' : undefined"
            @click="$emit('navigate')"
          >
            <span>{{ item.navTitle }}</span>
            <span v-if="item.audience === 'verwaltung'" class="size-2 shrink-0 rounded-full bg-amber-500" aria-label="Nur VERWALTUNG" />
          </NuxtLink>
        </li>
      </ul>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { documentationPath, getDocumentationGroups } from '~/utils/documentation'

defineProps<{ activeSlug: string }>()
defineEmits<{ navigate: [] }>()
const groups = getDocumentationGroups()
</script>
