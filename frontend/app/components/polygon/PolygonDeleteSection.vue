<template>
  <section class="rounded-2xl border border-rose-200 bg-rose-50/50 p-5 sm:p-6" aria-labelledby="polygon-danger-heading">
    <h2 id="polygon-danger-heading" class="text-lg font-bold text-rose-950">Gefahrenbereich</h2>
    <p class="mt-2 max-w-2xl text-sm leading-6 text-rose-900">Diese Fläche dauerhaft löschen. Die Aktion kann nicht rückgängig gemacht werden.</p>
    <button class="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border border-rose-300 bg-white px-4 text-sm font-bold text-rose-700 transition hover:bg-rose-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700" type="button" @click="dialogOpen = true">
      <Trash2 class="size-4" aria-hidden="true" /> Fläche löschen
    </button>

    <AppConfirmDialog
      v-model:open="dialogOpen"
      title="Fläche löschen?"
      :body="`„${name}“ wird dauerhaft gelöscht. Diese Aktion kann nicht rückgängig gemacht werden.`"
      confirm-label="Endgültig löschen"
      loading-label="Wird gelöscht …"
      variant="danger"
      :loading="loading"
      :error="error"
      @confirm="$emit('confirm')"
    />
  </section>
</template>

<script setup lang="ts">
import { Trash2 } from 'lucide-vue-next'

const props = defineProps<{ name: string, loading: boolean, error?: string }>()
defineEmits<{ confirm: [] }>()
const dialogOpen = ref(false)

watch(() => props.loading, (loading, previous) => {
  if (previous && !loading && !props.error) dialogOpen.value = false
})
</script>
