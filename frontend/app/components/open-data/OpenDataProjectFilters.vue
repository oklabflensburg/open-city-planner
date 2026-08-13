<template>
  <Card class="p-4 sm:p-5">
    <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_16rem_auto] md:items-end">
      <label class="block">
        <span class="field-label">Projekte durchsuchen</span>
        <span class="relative block">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input
            :value="search"
            type="search"
            class="field-input pl-10"
            placeholder="Titel, Thema oder Beschreibung"
            autocomplete="off"
            @input="$emit('update:search', ($event.target as HTMLInputElement).value)"
          >
        </span>
      </label>

      <label class="block">
        <span class="field-label">Kategorie</span>
        <select
          :value="category"
          class="field-input"
          @change="$emit('update:category', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">Alle Kategorien</option>
          <option v-for="item in categories" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <Button v-if="search || category" variant="secondary" class="w-full md:w-auto" @click="$emit('reset')">
        <RotateCcw class="size-4" aria-hidden="true" />
        Zurücksetzen
      </Button>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { RotateCcw, Search } from 'lucide-vue-next'

defineProps<{ search: string, category: string, categories: string[] }>()
defineEmits<{
  'update:search': [value: string]
  'update:category': [value: string]
  reset: []
}>()
</script>
