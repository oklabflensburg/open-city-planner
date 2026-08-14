<template>
  <section class="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-7">
    <div class="flex flex-col gap-5 sm:flex-row sm:items-center">
      <UserAvatar :user="previewUser" size="2xl" alt="Profilbild" loading="eager" />
      <div class="min-w-0 flex-1">
        <h2 class="text-lg font-bold text-[#202427]">Profilbild</h2>
        <p class="mt-1 text-sm leading-6 text-[#687176]">JPG, PNG oder WebP, maximal 5 MB.</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <label class="page-button-secondary cursor-pointer focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[#154d73]">
            <input
              class="sr-only"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              :disabled="uploading"
              @change="selectFile"
            >
            Profilbild ändern
          </label>
          <button
            class="page-button-primary disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="!file || uploading"
            @click="upload"
          >
            {{ uploading ? 'Speichert ...' : 'Speichern' }}
          </button>
          <button
            class="page-button-secondary disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="!authStore.user?.avatar_url || uploading"
            @click="openRemoveDialog"
          >
            Profilbild entfernen
          </button>
        </div>
        <p class="mt-3 text-sm text-[#687176]" aria-live="polite">{{ statusText }}</p>
        <p v-if="error" class="mt-3 rounded-md bg-[#fff1f0] px-3 py-2 text-sm font-semibold text-[#a12c24]" role="alert">{{ error }}</p>
      </div>
    </div>

    <AppConfirmDialog
      v-model:open="removeDialogOpen"
      title="Profilbild entfernen?"
      body="Das aktuelle Profilbild wird dauerhaft entfernt. Anschließend werden wieder deine Initialen angezeigt."
      confirm-label="Profilbild entfernen"
      loading-label="Wird entfernt …"
      variant="danger"
      :loading="uploading"
      :error="removeError"
      @confirm="remove"
    />
  </section>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const config = useRuntimeConfig()
const file = ref<File | null>(null)
const previewUrl = ref('')
const uploading = ref(false)
const error = ref('')
const statusText = ref('')
const removeDialogOpen = ref(false)
const removeError = ref('')

const previewUser = computed(() => ({
  ...(authStore.user ?? {
    email: '',
    first_name: '',
    last_name: '',
    display_name: null,
    avatar_url: null
  }),
  avatar_url: previewUrl.value || authStore.user?.avatar_url || null
}))

function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = input.files?.[0] ?? null
  input.value = ''
  clearPreview()
  error.value = ''
  statusText.value = ''
  if (!selected) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) {
    error.value = 'Bitte wähle ein JPG-, PNG- oder WebP-Bild aus.'
    return
  }
  if (selected.size > Number(config.public.avatarMaxUploadBytes)) {
    error.value = 'Das Profilbild darf maximal 5 MB groß sein.'
    return
  }
  file.value = selected
  previewUrl.value = URL.createObjectURL(selected)
  statusText.value = 'Vorschau bereit.'
}

async function upload() {
  if (!file.value || uploading.value) return
  uploading.value = true
  error.value = ''
  try {
    await authStore.uploadAvatar(file.value)
    statusText.value = 'Profilbild gespeichert.'
    file.value = null
    clearPreview()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Das Profilbild konnte nicht gespeichert werden.'
  } finally {
    uploading.value = false
  }
}

async function remove() {
  if (uploading.value) return
  uploading.value = true
  removeError.value = ''
  try {
    await authStore.deleteAvatar()
    statusText.value = 'Profilbild entfernt.'
    file.value = null
    clearPreview()
    removeDialogOpen.value = false
  } catch (err) {
    removeError.value = err instanceof Error ? err.message : 'Das Profilbild konnte nicht entfernt werden.'
  } finally {
    uploading.value = false
  }
}

function openRemoveDialog() {
  removeError.value = ''
  removeDialogOpen.value = true
}

function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
  file.value = null
}

onBeforeUnmount(clearPreview)
</script>
