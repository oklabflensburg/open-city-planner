<template>
  <img
    :class="{
      'h-9 w-auto md:h-10': size === 'compact',
      'h-auto w-[82px] md:w-[90px]': size === 'footer',
      'h-auto w-[150px] md:w-[178px]': size === 'default'
    }"
    src="/branding/ok-lab-flensburg.svg"
    alt="OK Lab Flensburg"
    width="178"
    height="178"
  >
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: 'compact' | 'default' | 'footer'
}>(), {
  size: 'default',
})
</script>
