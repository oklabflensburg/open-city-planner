<template>
  <section class="rounded-lg border border-[#dfe4e6] bg-white p-6">
    <div class="flex flex-col gap-5 sm:flex-row sm:items-center">
      <UserAvatar :user="previewUser" size="2xl" alt="Profilbild" loading="eager" />
      <div class="min-w-0 flex-1">
        <h2 class="text-lg font-bold text-[#202427]">Profilbild</h2>
        <p class="mt-1 text-sm leading-6 text-[#687176]">JPG, PNG oder WebP, maximal 5 MB.</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <label class="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-[#cfd8dc] px-4 text-sm font-bold text-[#30363a] transition hover:bg-[#f4f6f6] focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[#154d73]">
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
            class="min-h-11 rounded-md bg-[#154d73] px-4 text-sm font-bold text-white transition hover:bg-[#0f3f61] disabled:cursor-not-allowed disabled:bg-[#9eb5c4]"
            type="button"
            :disabled="!file || uploading"
            @click="upload"
          >
            {{ uploading ? 'Speichert ...' : 'Speichern' }}
          </button>
          <button
            class="min-h-11 rounded-md border border-[#cfd8dc] px-4 text-sm font-bold text-[#30363a] transition hover:bg-[#f4f6f6] disabled:cursor-not-allowed disabled:text-[#9aa2a6]"
            type="button"
            :disabled="!authStore.user?.avatar_url || uploading"
            @click="remove"
          >
            Profilbild entfernen
          </button>
        </div>
        <p class="mt-3 text-sm text-[#687176]" aria-live="polite">{{ statusText }}</p>
        <p v-if="error" class="mt-3 rounded-md bg-[#fff1f0] px-3 py-2 text-sm font-semibold text-[#a12c24]" role="alert">{{ error }}</p>
      </div>
    </div>
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
  error.value = ''
  try {
    await authStore.deleteAvatar()
    statusText.value = 'Profilbild entfernt.'
    file.value = null
    clearPreview()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Das Profilbild konnte nicht entfernt werden.'
  } finally {
    uploading.value = false
  }
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
