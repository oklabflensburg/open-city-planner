<template>
  <div>
    <h2 class="mb-3 text-[12px] font-semibold uppercase text-[#3f4448]">Etagen</h2>
    <div class="grid grid-cols-3 gap-1 text-center">
      <button
        v-for="floor in floors"
        :key="floor"
        class="min-h-11 rounded-md text-[13px] font-bold text-[#b4b6b9] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] md:min-h-8"
        :class="{ 'bg-white text-[#3f4448] shadow-sm': filter.selectedFloor === floor }"
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

