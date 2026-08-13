<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-40 bg-black/20 lg:hidden" @click="$emit('close')" />
    <aside
      class="fixed z-50 bg-white shadow-[0_8px_40px_rgba(0,0,0,0.18)] transition-transform duration-200 lg:hidden"
      :class="[
        side === 'bottom'
          ? 'inset-x-0 bottom-0 max-h-[72vh] rounded-t-[18px]'
          : 'inset-y-0 left-0 w-[min(340px,92vw)]',
        open ? 'translate-x-0 translate-y-0' : side === 'bottom' ? 'translate-y-full' : '-translate-x-full'
      ]"
      :aria-hidden="!open"
    >
      <slot />
    </aside>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{ open: boolean; side?: 'left' | 'bottom' }>()
defineEmits<{ close: [] }>()
</script>
