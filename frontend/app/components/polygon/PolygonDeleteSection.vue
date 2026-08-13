<template>
  <section class="rounded-2xl border border-rose-200 bg-rose-50/50 p-5 sm:p-6" aria-labelledby="polygon-danger-heading">
    <h2 id="polygon-danger-heading" class="text-lg font-bold text-rose-950">Gefahrenbereich</h2>
    <p class="mt-2 max-w-2xl text-sm leading-6 text-rose-900">Diese Fläche dauerhaft löschen. Die Aktion kann nicht rückgängig gemacht werden.</p>
    <p v-if="error" class="mt-3 rounded-lg border border-rose-200 bg-white px-4 py-3 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
    <button ref="deleteButton" class="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border border-rose-300 bg-white px-4 text-sm font-bold text-rose-700 transition hover:bg-rose-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700" type="button" @click="openDialog">
      <Trash2 class="size-4" aria-hidden="true" /> Fläche löschen
    </button>

    <Teleport to="body">
      <div v-if="dialogOpen" class="fixed inset-0 z-[120] grid place-items-center bg-slate-950/45 p-4" @click.self="closeDialog">
        <section class="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" role="alertdialog" aria-modal="true" aria-labelledby="delete-dialog-title" aria-describedby="delete-dialog-description" @keydown.esc="closeDialog">
          <div class="flex size-11 items-center justify-center rounded-full bg-rose-100 text-rose-700"><Trash2 class="size-5" aria-hidden="true" /></div>
          <h2 id="delete-dialog-title" class="mt-4 text-xl font-bold text-slate-950">Fläche löschen?</h2>
          <p id="delete-dialog-description" class="mt-3 leading-7 text-slate-600">„{{ name }}“ wird dauerhaft gelöscht. Diese Aktion kann nicht rückgängig gemacht werden.</p>
          <p v-if="error" class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
          <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button class="min-h-11 rounded-xl border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50" type="button" :disabled="loading" @click="closeDialog">Abbrechen</button>
            <button ref="confirmButton" class="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-rose-700 px-4 text-sm font-bold text-white hover:bg-rose-800 disabled:cursor-wait disabled:opacity-60" type="button" :disabled="loading" @click="$emit('confirm')">
              <LoaderCircle v-if="loading" class="size-4 animate-spin" aria-hidden="true" />
              {{ loading ? 'Wird gelöscht …' : 'Endgültig löschen' }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { LoaderCircle, Trash2 } from 'lucide-vue-next'

const props = defineProps<{ name: string, loading: boolean, error?: string }>()
defineEmits<{ confirm: [] }>()
const dialogOpen = ref(false)
const deleteButton = ref<HTMLButtonElement | null>(null)
const confirmButton = ref<HTMLButtonElement | null>(null)

function openDialog() {
  dialogOpen.value = true
  nextTick(() => confirmButton.value?.focus())
}

function closeDialog() {
  if (props.loading) return
  dialogOpen.value = false
  nextTick(() => deleteButton.value?.focus())
}

watch(() => props.loading, (loading, previous) => {
  if (previous && !loading && !props.error) dialogOpen.value = false
})
</script>
