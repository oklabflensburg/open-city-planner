<template>
  <nav aria-label="Auf dieser Seite">
    <p class="mb-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Auf dieser Seite</p>
    <ol class="space-y-2 border-l border-slate-200 pl-4">
      <li v-for="section in sections" :key="section.id">
        <a class="text-sm leading-5 text-slate-600 hover:text-[#154d73] hover:underline" :href="`#${section.id}`">
          {{ section.title }}
        </a>
      </li>
    </ol>
  </nav>
</template>

<script setup lang="ts">
import type { DocumentationSection } from '~/types/documentation'
defineProps<{ sections: DocumentationSection[] }>()
</script>
