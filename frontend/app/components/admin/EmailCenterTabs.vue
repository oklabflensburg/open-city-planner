<template>
  <nav class="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3" aria-label="E-Mail-Zentrale">
    <NuxtLink v-for="item in items" :key="item.to" class="rounded-lg px-4 py-2 text-sm font-bold" :class="active(item.to) ? 'bg-[#154d73] text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'" :to="item.to">{{ item.label }}</NuxtLink>
  </nav>
</template>

<script setup lang="ts">
const route = useRoute()
const items = [
  { label: 'Vorlagen', to: '/admin/email-vorlagen' },
  { label: 'Rundmails', to: '/admin/email-zentrale/rundmails' },
  { label: 'Versand', to: '/admin/email-zentrale/versand' }
]
const active = (to: string) => route.path.startsWith(to)
</script>
