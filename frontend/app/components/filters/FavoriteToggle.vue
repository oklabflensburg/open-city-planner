<template>
  <button
    class="flex min-h-11 w-full cursor-pointer items-center justify-between text-[12px] font-semibold uppercase tracking-normal text-[#3f4448] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73] md:min-h-8"
    type="button"
    :aria-pressed="filter.favoriteOnly"
    @click="filter.favoriteOnly = !filter.favoriteOnly"
  >
    <span>Meine Favoriten</span>
    <Star class="size-5" :class="filter.favoriteOnly ? 'fill-[#ffc20e] text-[#ffc20e]' : 'text-[#8e9398]'" />
  </button>
</template>

<script setup lang="ts">
import { Star } from 'lucide-vue-next'

const filter = useFilterStore()
</script>
