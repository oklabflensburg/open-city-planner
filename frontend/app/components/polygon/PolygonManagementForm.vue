<template>
  <section class="rounded-xl border border-[#d7c9aa] bg-[#fffdf7] p-6" aria-labelledby="management-heading">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-xs font-bold uppercase tracking-wide text-[#7b6333]">Nur VERWALTUNG</p>
        <h2 id="management-heading" class="mt-1 text-lg font-bold text-[#202427]">Verwaltungsdaten</h2>
      </div>
      <span class="text-xs text-[#687176]">Nicht öffentlich · nicht im SEO</span>
    </div>
    <div class="mt-5 grid gap-4 sm:grid-cols-2">
      <label class="sm:col-span-2">
        <span class="field-label">Fachlicher Eigentümer</span>
        <input v-model="model.owner_name" class="field-input" maxlength="200" @input="changed('owner_name')">
      </label>
      <label>
        <span class="field-label">Straße</span>
        <input v-model="model.owner_street" class="field-input" maxlength="160" @input="changed('owner_street')">
      </label>
      <label>
        <span class="field-label">Hausnummer</span>
        <input v-model="model.owner_house_number" class="field-input" maxlength="40" @input="changed('owner_house_number')">
      </label>
      <label>
        <span class="field-label">PLZ</span>
        <input v-model="model.owner_postal_code" class="field-input" maxlength="32" @input="changed('owner_postal_code')">
      </label>
      <label>
        <span class="field-label">Ort</span>
        <input v-model="model.owner_city" class="field-input" maxlength="120" @input="changed('owner_city')">
      </label>
      <label>
        <span class="field-label">Land</span>
        <input v-model="model.owner_country" class="field-input" maxlength="120" @input="changed('owner_country')">
      </label>
      <label>
        <span class="field-label">Quadratmeterpreis (€/m²)</span>
        <input
          v-model="model.price_per_sqm"
          class="field-input"
          type="number"
          min="0"
          step="0.01"
          inputmode="decimal"
          @input="changed('price_per_sqm')"
        >
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { PolygonVerwaltungDetail } from '~/types/geo'

const model = defineModel<PolygonVerwaltungDetail>({ required: true })
const emit = defineEmits<{ change: [field: keyof PolygonVerwaltungDetail, value: unknown] }>()

function changed(field: keyof PolygonVerwaltungDetail) {
  emit('change', field, model.value[field] === '' ? null : model.value[field])
}
</script>

<style scoped>
.field-label { display: block; margin-bottom: 0.35rem; font-size: 0.8rem; font-weight: 700; color: #4f575c; }
.field-input { min-height: 2.75rem; width: 100%; border: 1px solid #cfd6d9; border-radius: 0.45rem; background: white; padding: 0.6rem 0.75rem; color: #202427; }
.field-input:focus { border-color: #154d73; outline: 2px solid rgb(21 77 115 / 18%); outline-offset: 1px; }
</style>
