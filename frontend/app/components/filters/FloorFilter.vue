<template>
  <div>
    <h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Etagen</h3>
    <div class="grid grid-cols-3 gap-2 text-center">
      <button
        v-for="floor in floors"
        :key="floor"
        class="min-h-10 rounded-lg border border-slate-200 bg-white text-xs font-bold text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
        :class="{ '!border-[#6f9fbd] !bg-[#edf4f8] !text-[#154d73] shadow-sm': filter.selectedFloor === floor }"
        type="button"
        @click="filter.selectedFloor = floor"
      >
        {{ floor }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const filter = useFilterStore()
const floors = ['UG', 'EG', 'OG'] as const
</script>
