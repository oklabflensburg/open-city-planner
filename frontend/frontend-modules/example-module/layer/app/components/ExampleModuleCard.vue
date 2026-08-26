<template>
  <Card class="p-5 sm:p-7" data-example-module-card>
    <h2 class="text-xl font-black text-slate-950">Gemeinsame Host-Primitives</h2>
    <p class="mt-3 leading-7 text-slate-600">Diese Komponente stammt aus dem Example-Modul und verwendet Card und Button aus dem gemeinsamen Designsystem.</p>
    <p class="mt-3 font-semibold text-slate-800" aria-live="polite">{{ greeting }}</p>
    <Button class="mt-5" variant="primary" @click="store.increment">Pinia-Status aktualisieren</Button>
  </Card>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useExampleModuleGreeting } from '../composables/useExampleModuleGreeting'
import { useExampleModuleStore } from '../stores/exampleModule'

const store = useExampleModuleStore()
const { count } = storeToRefs(store)
const greeting = useExampleModuleGreeting(count)
</script>
