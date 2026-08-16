<template>
  <a
    :href="projectConfig.social.mastodon.url"
    target="_blank"
    :rel="identity ? 'me noopener noreferrer' : 'noopener noreferrer'"
    :class="variantClasses[variant]"
    :aria-label="`${label} ${projectConfig.social.mastodon.handle} (öffnet in einem neuen Tab)`"
  >
    <MessageCircle class="size-4 shrink-0" aria-hidden="true" />
    <span>{{ label }}</span>
    <ExternalLink class="size-4 shrink-0" aria-hidden="true" />
  </a>
</template>

<script setup lang="ts">
import { ExternalLink, MessageCircle } from 'lucide-vue-next'
import { projectConfig } from '~/config/project'

withDefaults(defineProps<{
  identity?: boolean
  label?: string
  variant?: 'button' | 'link' | 'footer'
}>(), {
  identity: false,
  label: 'Mastodon',
  variant: 'link'
})

const variantClasses = {
  button: 'page-button-secondary w-full sm:w-auto',
  link: 'inline-flex min-h-11 items-center gap-2 font-bold text-[#154d73] underline decoration-[#6f9db8] underline-offset-4 transition hover:text-[#0d3a57] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]',
  footer: 'inline-flex min-h-11 items-center gap-2 text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]'
} as const
</script>
