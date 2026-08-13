<template>
  <section class="scroll-mt-24" :aria-labelledby="headingId">
    <div v-if="title || description" class="mb-5 max-w-3xl">
      <h2 v-if="title" :id="headingId" class="text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">{{ title }}</h2>
      <p v-if="description" class="mt-2 leading-7 text-slate-600">{{ description }}</p>
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{ title?: string, description?: string, id?: string }>()
const headingId = computed(() => props.id || (props.title ? `section-${props.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}` : undefined))
</script>
