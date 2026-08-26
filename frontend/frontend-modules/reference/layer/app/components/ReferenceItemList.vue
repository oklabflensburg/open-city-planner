<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="reference-items-title">
    <h2 id="reference-items-title" class="text-xl font-bold text-slate-900">Marker aus der Modul-API</h2>
    <p class="mt-1 text-sm leading-6 text-slate-600">
      Diese Einträge werden serverseitig aus der eigenen Tabelle des Moduls geladen.
    </p>
    <p v-if="pending" class="mt-4 text-sm text-slate-600" role="status">Referenzmarker werden geladen …</p>
    <p v-else-if="error" class="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">
      Die Referenzmarker konnten nicht geladen werden.
    </p>
    <ul v-else class="mt-4 grid gap-3 sm:grid-cols-2">
      <li v-for="item in items" :key="item.id" class="rounded-xl border border-slate-200 p-4">
        <h3 class="font-bold text-slate-900">{{ item.title }}</h3>
        <p class="mt-1 text-sm leading-6 text-slate-600">{{ item.description }}</p>
        <p class="mt-2 font-mono text-xs text-slate-500">{{ item.latitude.toFixed(4) }}, {{ item.longitude.toFixed(4) }}</p>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { ReferenceItemRead } from '../composables/useReferenceItems'

defineProps<{
  items: readonly ReferenceItemRead[]
  pending: boolean
  error: boolean
}>()
</script>
