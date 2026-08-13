<template>
  <section class="mx-auto w-full max-w-[460px] rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm sm:p-8">
    <p class="mb-2 text-xs font-bold uppercase tracking-[0.12em] text-[#154d73]">{{ eyebrow }}</p>
    <h1 class="text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">{{ title }}</h1>
    <div class="mt-6">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
}>()
</script>
