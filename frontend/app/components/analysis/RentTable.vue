<template>
  <Card class="overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3">
      <h2 class="text-[13px] font-semibold text-[#3f4448]">Spitzenmieten in den Teillagen (€/qm)</h2>
      <Info class="size-4 text-[#9aa0a5]" />
    </div>
    <div class="overflow-x-auto">
      <table class="w-full min-w-[330px] text-left text-[11px]">
        <thead class="bg-[#e9e9e7] text-[#656b70]">
          <tr>
            <th class="px-4 py-2 font-semibold">Lage</th>
            <th v-for="size in sizes" :key="size" class="px-3 py-2 text-right font-semibold">{{ size }}</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-t border-[#ececec]">
            <td class="px-4 py-3 text-[#3f4448]">Holm / Große Straße</td>
            <td class="px-3 py-3 text-right">84</td>
            <td class="px-3 py-3 text-right">61</td>
            <td class="px-3 py-3 text-right">43</td>
            <td class="px-3 py-3 text-right">26</td>
          </tr>
        </tbody>
      </table>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'

const sizes = ['S', 'M', 'L', 'XL']
</script>

