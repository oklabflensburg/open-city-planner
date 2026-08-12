<template>
  <section class="mx-auto w-full max-w-[460px] rounded-lg border border-[#dfe4e6] bg-white p-6 shadow-[0_1px_16px_rgba(20,24,28,0.08)]">
    <p class="mb-2 text-xs font-bold uppercase text-[#687176]">{{ eyebrow }}</p>
    <h1 class="text-2xl font-bold text-[#202427]">{{ title }}</h1>
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
