<template>
  <NuxtLink
    class="inline-flex min-h-11 items-center rounded-xl border border-[#154d73] bg-white px-3 text-sm font-bold text-[#154d73] transition hover:bg-[#edf4f8] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
    to="/module-example"
    aria-label="Frontend-Modulbeispiel öffnen"
  >
    {{ label }}
  </NuxtLink>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: 'Modulbeispiel' })
</script>
