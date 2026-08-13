<template>
  <aside class="flex h-full min-h-0 flex-col gap-3">
    <section class="min-h-0 overflow-y-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm">
      <header class="flex items-center gap-2 border-b border-slate-100 px-4 py-4">
        <ListFilter class="size-4 text-[#154d73]" aria-hidden="true" />
        <h2 class="text-sm font-bold text-slate-800">Filter &amp; Ansichten</h2>
      </header>
      <div class="space-y-6 px-4 py-5">
        <AreaFilter />
        <FloorFilter />
        <IndustryFilter />
      </div>
    </section>
    <section class="shrink-0 rounded-2xl border border-sky-100 bg-white p-4 shadow-sm" aria-labelledby="filter-hint-title">
      <div class="flex items-center gap-2 text-[#154d73]">
        <Info class="size-4" aria-hidden="true" />
        <h2 id="filter-hint-title" class="text-sm font-bold">Hinweis</h2>
      </div>
      <p class="mt-2 text-xs leading-5 text-slate-600">
        Für Detailinformationen und Bearbeitung wählen Sie ein Polygon auf der Karte aus, um zur Detailseite zu gelangen.
      </p>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { Info, ListFilter } from 'lucide-vue-next'
</script>
