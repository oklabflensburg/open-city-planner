<template>
  <article class="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
    <p class="mb-3 text-xs font-bold uppercase text-[#687176]">Rechtliches</p>
    <h1 class="text-3xl font-bold text-[#202427] md:text-4xl">{{ title }}</h1>
    <p v-if="intro" class="mt-4 max-w-3xl text-sm leading-6 text-[#596166] md:text-base">
      {{ intro }}
    </p>
    <div class="mt-8 space-y-8 rounded-lg border border-[#e2e4e5] bg-white p-5 shadow-[0_1px_12px_rgba(20,24,28,0.06)] sm:p-7">
      <slot />
    </div>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  intro?: string
}>()
</script>
