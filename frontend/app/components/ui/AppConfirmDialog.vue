<template>
  <AppModal
    :open="open"
    :title="title"
    :description="description"
    :described-by="body || $slots.default ? bodyId : undefined"
    size="sm"
    role="alertdialog"
    :busy="loading"
    :close-on-overlay="closeOnOverlay"
    :show-close="false"
    @update:open="updateOpen"
    @close="$emit('cancel')"
  >
    <div class="flex items-start gap-4">
      <div class="grid size-11 shrink-0 place-items-center rounded-full" :class="iconClass">
        <component :is="icon" class="size-5" aria-hidden="true" />
      </div>
      <div :id="bodyId" class="min-w-0 flex-1 text-sm leading-6 text-slate-700">
        <slot>{{ body }}</slot>
      </div>
    </div>

    <p v-if="error" class="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>

    <template #footer>
      <div class="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <Button data-autofocus :disabled="loading" @click="cancel">{{ cancelLabel }}</Button>
        <Button :variant="buttonVariant" :disabled="loading" @click="$emit('confirm')">
          <LoaderCircle v-if="loading" class="size-4 animate-spin" aria-hidden="true" />
          {{ loading ? loadingLabel : confirmLabel }}
        </Button>
      </div>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { AlertTriangle, CircleHelp, LoaderCircle, ShieldAlert } from 'lucide-vue-next'

type ConfirmVariant = 'default' | 'warning' | 'danger'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  body?: string
  confirmLabel?: string
  cancelLabel?: string
  loadingLabel?: string
  variant?: ConfirmVariant
  loading?: boolean
  error?: string
  closeOnOverlay?: boolean
}>(), {
  body: '',
  confirmLabel: 'Bestätigen',
  cancelLabel: 'Abbrechen',
  loadingLabel: 'Wird ausgeführt …',
  variant: 'default',
  loading: false,
  error: '',
  closeOnOverlay: true
})

const emit = defineEmits<{
  'update:open': [open: boolean]
  confirm: []
  cancel: []
}>()

const bodyId = `app-confirm-body-${useId()}`
const icon = computed(() => ({ default: CircleHelp, warning: ShieldAlert, danger: AlertTriangle })[props.variant])
const iconClass = computed(() => ({
  default: 'bg-sky-100 text-sky-800',
  warning: 'bg-amber-100 text-amber-800',
  danger: 'bg-rose-100 text-rose-700'
})[props.variant])
const buttonVariant = computed(() => props.variant === 'danger' ? 'danger' : 'primary')

function updateOpen(open: boolean) {
  emit('update:open', open)
}

function cancel() {
  if (props.loading) return
  emit('update:open', false)
  emit('cancel')
}
</script>
