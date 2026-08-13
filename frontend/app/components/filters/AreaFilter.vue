<template>
  <div>
    <h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Verkaufsfläche</h3>
    <div class="grid grid-cols-4 gap-2 text-center">
      <button
        v-for="size in sizes"
        :key="size"
        class="min-h-11 rounded-lg border border-slate-200 bg-white text-xs font-bold text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] lg:min-h-10"
        :class="{ '!border-[#6f9fbd] !bg-[#edf4f8] !text-[#154d73] shadow-sm': filter.selectedSize === size }"
        type="button"
        @click="filter.selectedSize = size"
      >
        {{ size }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const filter = useFilterStore()
const sizes = ['S', 'M', 'L', 'XL'] as const
</script>
