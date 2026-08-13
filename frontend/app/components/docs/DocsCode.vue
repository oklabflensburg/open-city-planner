<template>
  <div class="my-5 overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
    <div v-if="language" class="border-b border-slate-800 px-4 py-2 text-xs font-bold uppercase tracking-wider text-slate-400">
      {{ language }}
    </div>
    <pre class="overflow-x-auto p-4 text-sm leading-6 text-slate-100"><code>{{ code }}</code></pre>
  </div>
</template>

<script setup lang="ts">
defineProps<{ code: string, language?: string }>()
</script>
