<template>
  <StatusBadge :tone="tone">{{ label }}</StatusBadge>
</template>

<script setup lang="ts">
import type { DocumentationAudience } from '~/types/documentation'

const props = defineProps<{ audience: DocumentationAudience }>()

const label = computed(() => ({
  public: 'Öffentlich',
  login: 'Anmeldung erforderlich',
  verwaltung: 'Nur VERWALTUNG'
})[props.audience])

const audienceTones = {
  public: 'success',
  login: 'info',
  verwaltung: 'warning'
} as const
const tone = computed(() => audienceTones[props.audience])
</script>
