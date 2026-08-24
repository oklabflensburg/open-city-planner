<template>
  <a
    :href="href"
    target="_blank"
    rel="noopener noreferrer"
    :class="variantClasses[variant]"
    :aria-label="`${label} (öffnet in einem neuen Tab)`"
  >
    <ProviderIcon provider="github" class="size-4" />
    <span>{{ label }}</span>
    <ExternalLink class="size-4 shrink-0" aria-hidden="true" />
  </a>
</template>

<script setup lang="ts">
import { ExternalLink } from '@lucide/vue'
import { projectConfig } from '~/config/project'

const props = withDefaults(defineProps<{
  destination?: 'repository' | 'issues' | 'contributing'
  label?: string
  variant?: 'button' | 'link' | 'footer'
}>(), {
  destination: 'repository',
  label: 'Quellcode auf GitHub',
  variant: 'link'
})

const href = computed(() => {
  if (props.destination === 'issues') return projectConfig.github.issuesUrl
  if (props.destination === 'contributing') return projectConfig.github.contributingUrl
  return projectConfig.github.url
})

const variantClasses = {
  button: 'page-button-secondary w-full sm:w-auto',
  link: 'inline-flex min-h-11 items-center gap-2 font-bold text-[#154d73] underline decoration-[#6f9db8] underline-offset-4 transition hover:text-[#0d3a57] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]',
  footer: 'inline-flex min-h-11 items-center gap-2 text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]'
} as const
</script>
