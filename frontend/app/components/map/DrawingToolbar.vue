<template>
  <div class="pointer-events-auto flex gap-1 rounded-[12px] border border-[#e4e4e4] bg-white p-1 shadow-[0_1px_10px_rgba(20,24,28,0.12)]">
    <button
      v-for="tool in tools"
      :key="tool.mode"
      class="grid min-h-11 min-w-11 place-items-center rounded-[9px] text-[#34383c] transition hover:bg-[#f3f3f3] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] md:min-h-9 md:min-w-9"
      :class="{ 'bg-[#edf4f8] text-[#154d73]': mapStore.activeMode === tool.mode, 'cursor-not-allowed opacity-45': !canUseTool(tool.mode) }"
      type="button"
      :aria-label="tool.label"
      :title="toolTitle(tool.mode, tool.label)"
      :disabled="!canUseTool(tool.mode)"
      @click="activate(tool.mode)"
    >
      <component :is="tool.icon" class="size-4" />
    </button>
    <NuxtLink
      v-if="!authStore.authenticated"
      class="inline-flex min-h-11 items-center rounded-[9px] px-3 text-xs font-bold text-[#154d73] transition hover:bg-[#edf4f8] md:min-h-9"
      :to="`/login?redirect=${encodeURIComponent(route.fullPath)}`"
    >
      Zum Bearbeiten anmelden
    </NuxtLink>
    <button
      v-else-if="needsEmailVerification(authStore.user)"
      class="inline-flex min-h-11 items-center rounded-[9px] px-3 text-xs font-bold text-[#154d73] transition hover:bg-[#edf4f8] md:min-h-9"
      type="button"
      @click="authStore.resendVerification()"
    >
      E-Mail bestätigen
    </button>
  </div>
</template>

<script setup lang="ts">
import { MousePointer2, Pencil, Pentagon, Trash2 } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { DrawingMode } from '~/stores/map'

const mapStore = useMapStore()
const polygonStore = usePolygonStore()
const authStore = useAuthStore()
const route = useRoute()
const tools: Array<{ mode: DrawingMode; label: string; icon: Component }> = [
  { mode: 'select', label: 'Polygon auswählen', icon: MousePointer2 },
  { mode: 'polygon', label: 'Polygon zeichnen', icon: Pentagon },
  { mode: 'edit', label: 'Polygon bearbeiten', icon: Pencil },
  { mode: 'delete', label: 'Polygon löschen', icon: Trash2 }
]

const activate = (mode: DrawingMode) => {
  if (!canUseTool(mode)) return
  mapStore.setMode(mode)
}

function canUseTool(mode: DrawingMode) {
  if (mode === 'select') return true
  if (!authStore.canWrite) return false
  if (mode === 'polygon') return true
  const polygon = polygonStore.selectedPolygon
  if (!polygon) return false
  return authStore.user?.is_superuser
    || authStore.user?.roles?.some(role => role.trim().toUpperCase() === 'VERWALTUNG')
    || polygon.created_by_user_id === authStore.user?.id
}

function toolTitle(mode: DrawingMode, label: string) {
  if (canUseTool(mode)) return label
  if (!authStore.authenticated) return 'Zum Bearbeiten anmelden'
  if (needsEmailVerification(authStore.user)) return 'Bitte bestätige zuerst deine E-Mail-Adresse.'
  return 'Du kannst nur eigene Flächen bearbeiten.'
}
</script>
