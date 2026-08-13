<template>
  <div>
    <section v-for="section in page.sections" :id="section.id" :key="section.id" class="scroll-mt-24 border-t border-slate-200 py-8 first:border-t-0 first:pt-0">
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <h2 class="group text-2xl font-bold tracking-tight text-slate-950">
          {{ section.title }}
          <a class="ml-1 text-slate-300 opacity-0 transition group-hover:opacity-100 focus:opacity-100" :href="`#${section.id}`" :aria-label="`Link zu ${section.title}`">#</a>
        </h2>
        <DocsRoleBadge v-if="section.audience" :audience="section.audience" />
      </div>

      <template v-for="(block, index) in section.blocks" :key="index">
        <p v-if="block.type === 'paragraph'" class="my-4 leading-7 text-slate-700">{{ block.text }}</p>
        <component :is="block.ordered ? 'ol' : 'ul'" v-else-if="block.type === 'list'" class="my-4 space-y-2 pl-6 leading-7 text-slate-700" :class="block.ordered ? 'list-decimal' : 'list-disc'">
          <li v-for="item in block.items" :key="item">{{ item }}</li>
        </component>
        <ol v-else-if="block.type === 'steps'" class="my-5 space-y-4">
          <li v-for="(item, stepIndex) in block.items" :key="item.title" class="grid grid-cols-[2rem_1fr] gap-3">
            <span class="flex size-8 items-center justify-center rounded-full bg-[#154d73] text-sm font-bold text-white">{{ stepIndex + 1 }}</span>
            <div><p class="font-bold text-slate-950">{{ item.title }}</p><p class="mt-1 leading-7 text-slate-700">{{ item.text }}</p></div>
          </li>
        </ol>
        <DocsCallout v-else-if="block.type === 'callout'" :variant="block.variant" :title="block.title" :text="block.text" />
        <DocsCode v-else-if="block.type === 'code'" :code="block.code" :language="block.language" />
        <figure v-else-if="block.type === 'image'" class="my-6 overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
          <img class="h-auto w-full" :src="block.src" :alt="block.alt" loading="lazy">
          <figcaption v-if="block.caption" class="border-t border-slate-200 px-4 py-3 text-sm leading-6 text-slate-600">{{ block.caption }}</figcaption>
        </figure>
        <div v-else-if="block.type === 'links'" class="my-5 grid gap-3 sm:grid-cols-2">
          <NuxtLink v-for="item in block.items" :key="item.to" :to="item.to" class="rounded-xl border border-slate-200 p-4 transition hover:border-[#4f86a8] hover:bg-[#f4f8fa] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]">
            <span class="flex items-center justify-between gap-3 font-bold text-[#154d73]">{{ item.label }}<ArrowRight class="size-4 shrink-0" aria-hidden="true" /></span>
            <span v-if="item.description" class="mt-1 block text-sm leading-6 text-slate-600">{{ item.description }}</span>
          </NuxtLink>
        </div>
        <div v-else-if="block.type === 'table'" class="my-5 overflow-x-auto rounded-xl border border-slate-200">
          <table class="min-w-full border-collapse text-left text-sm">
            <thead class="bg-slate-100 text-slate-950"><tr><th v-for="header in block.headers" :key="header" scope="col" class="px-4 py-3 font-bold">{{ header }}</th></tr></thead>
            <tbody class="divide-y divide-slate-200"><tr v-for="(row, rowIndex) in block.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex" class="px-4 py-3 align-top leading-6 text-slate-700">{{ cell }}</td></tr></tbody>
          </table>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import type { DocumentationPage } from '~/types/documentation'
defineProps<{ page: DocumentationPage }>()
</script>
