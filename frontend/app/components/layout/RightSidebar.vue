<template>
  <aside class="min-w-0 bg-[var(--c-surface)] lg:h-full lg:min-h-0 lg:overflow-hidden" aria-label="Kartenauswahl">
    <div class="min-w-0 pr-1 lg:h-full lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain">
      <MapSelectionContent />
    </div>
  </aside>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
</script>
