<template>
  <span
    class="inline-grid shrink-0 place-items-center overflow-hidden rounded-full bg-[#e8f1f4] font-bold text-[#154d73] ring-1 ring-[#d6e1e5]"
    :class="[sizeClass, textClass]"
  >
    <img
      v-if="src"
      class="size-full object-cover"
      :src="src"
      :alt="alt"
      :loading="loading"
      @error="imageFailed = true"
    >
    <span v-else>{{ initials }}</span>
  </span>
</template>

<script setup lang="ts">
import type { AuthUser } from '~/types/auth'
import { getUserInitials, resolveAvatarUrl } from '~/utils/user'

const props = withDefaults(defineProps<{
  user: Pick<AuthUser, 'display_name' | 'first_name' | 'last_name' | 'email' | 'avatar_url'> | null
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'
  alt?: string
  loading?: 'eager' | 'lazy'
}>(), {
  size: 'md',
  alt: '',
  loading: 'lazy'
})

const config = useRuntimeConfig()
const imageFailed = ref(false)
const initials = computed(() => getUserInitials(props.user) || '?')
const src = computed(() => {
  if (imageFailed.value) return ''
  return resolveAvatarUrl(props.user?.avatar_url, {
    apiBaseUrl: config.public.apiBaseUrl,
    mediaBaseUrl: config.public.mediaBaseUrl
  })
})

watch(() => props.user?.avatar_url, () => {
  imageFailed.value = false
})

const sizeClass = computed(() => ({
  xs: 'size-6',
  sm: 'size-8',
  md: 'size-10',
  lg: 'size-16',
  xl: 'size-24',
  '2xl': 'size-32'
}[props.size]))

const textClass = computed(() => ({
  xs: 'text-[10px]',
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-lg',
  xl: 'text-2xl',
  '2xl': 'text-3xl'
}[props.size]))
</script>
