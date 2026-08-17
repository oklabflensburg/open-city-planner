<template>
  <section class="civic-card mx-auto w-full max-w-[460px] rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm sm:p-8">
    <p class="civic-kicker mb-2">{{ eyebrow }}</p>
    <h1 class="text-2xl font-black tracking-tight text-[var(--c-text)] sm:text-3xl">{{ title }}</h1>
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
