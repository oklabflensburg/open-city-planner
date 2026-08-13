<template>
  <ContentPageShell title="Neue Fläche anlegen" description="Zeichnen Sie die Geometrie und ergänzen Sie die ersten öffentlichen Angaben. Nach dem Erstellen wechseln Sie automatisch zur Detailseite mit Autosave." eyebrow="Flächenverwaltung" :breadcrumbs="[{ label: 'Karte', to: '/' }, { label: 'Neue Fläche' }]" max-width="wide">
      <ol class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Arbeitsschritte">
        <li v-for="(step, index) in steps" :key="step" class="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700"><span class="grid size-7 shrink-0 place-items-center rounded-full bg-[#154d73] text-xs font-bold text-white">{{ index + 1 }}</span>{{ step }}</li>
      </ol>

      <form class="mt-6 grid min-w-0 items-start gap-6 sm:mt-8 xl:grid-cols-[minmax(0,1fr)_360px]" @submit.prevent="submit">
        <PolygonCreateMap :color="categoryColor" @update:geometry="geometry = $event" />

        <Card class="p-5 sm:p-6 xl:sticky xl:top-24">
          <h2 class="text-lg font-bold text-slate-950">Erste Angaben</h2>
          <div class="mt-5 space-y-5">
            <label class="block"><span class="field-label">Etage</span><select v-model="floor" class="field-input"><option v-for="item in floors" :key="item" :value="item">{{ item }}</option></select></label>
            <label class="block"><span class="field-label">Titel</span><input v-model.trim="name" class="field-input" maxlength="160" required placeholder="Zum Beispiel Ladenfläche Holm"></label>
            <label class="block"><span class="field-label">Kategorie</span><select v-model="category" class="field-input"><option v-for="industry in industries" :key="industry.key" :value="industry.key">{{ industry.label }}</option></select></label>
            <PolygonCategoryBadge :category="category" />
          </div>

          <p v-if="error" class="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
          <button class="page-button-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50" type="submit" :disabled="!canSubmit || submitting">
            <LoaderCircle v-if="submitting" class="size-4 animate-spin" aria-hidden="true" />
            <Plus v-else class="size-4" aria-hidden="true" />
            {{ submitting ? 'Fläche wird erstellt …' : 'Fläche erstellen' }}
          </button>
          <p v-if="!geometry" class="mt-3 text-center text-xs leading-5 text-slate-500">Zeichnen Sie zuerst ein gültiges Polygon auf der Karte.</p>
        </Card>
      </form>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { LoaderCircle, Plus } from 'lucide-vue-next'
import type { PolygonGeometry } from '~/types/geo'
import type { IndustryKey } from '~/utils/industries'
import { getIndustryColor, industries } from '~/utils/industries'

definePageMeta({ middleware: 'auth' })
usePageSeo({
  title: 'Neue Fläche anlegen',
  description: 'Neue Polygonfläche im Stadtplaner anlegen.',
  path: '/flaechen/neu',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})

const polygonApi = usePolygonApi()
const name = ref('Neue Fläche')
const floor = ref('EG')
const category = ref<IndustryKey>('otherAreas')
const geometry = shallowRef<PolygonGeometry | null>(null)
const submitting = ref(false)
const error = ref('')
const floors = ['UG', 'EG', '1OG', '2OG', '3OG', 'DG']
const steps = ['Fläche zeichnen', 'Etage auswählen', 'Titel vergeben', 'Fläche erstellen']
const categoryColor = computed(() => getIndustryColor(category.value))
const canSubmit = computed(() => !!geometry.value && !!name.value.trim())

async function submit() {
  if (!canSubmit.value || !geometry.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const created = await polygonApi.create({
      name: name.value.trim(),
      floor: floor.value,
      category: category.value,
      geometry: geometry.value,
      properties: {}
    })
    await navigateTo(`/flaechen/${created.slug}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Die Fläche konnte nicht erstellt werden.'
  } finally {
    submitting.value = false
  }
}
</script>
