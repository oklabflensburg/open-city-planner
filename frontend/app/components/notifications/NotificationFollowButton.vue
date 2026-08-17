<template>
  <button class="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-[#154d73] hover:bg-slate-50 disabled:opacity-60" type="button" :aria-pressed="following" :disabled="loading" @click="toggle">
    <BellRing v-if="following" class="size-4" aria-hidden="true" /><BellPlus v-else class="size-4" aria-hidden="true" />
    {{ following ? followedLabel : followLabel }}
  </button>
</template>

<script setup lang="ts">
import { BellPlus, BellRing } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  resourceType: 'POLYGON' | 'AREA'
  resourceId: string
  followLabel?: string
  followedLabel?: string
}>(), { followLabel: 'Folgen', followedLabel: 'Wird beobachtet' })
const store = useNotificationsStore()
const loading = ref(false)
const following = computed(() => store.isFollowing(props.resourceType, props.resourceId))

async function toggle() {
  loading.value = true
  try {
    if (following.value) await store.unfollow(props.resourceType, props.resourceId)
    else await store.follow(props.resourceType, props.resourceId)
    store.showToast({ title: following.value ? 'Benachrichtigungen aktiviert' : 'Benachrichtigungen deaktiviert', priority: 'SUCCESS' })
  } finally {
    loading.value = false
  }
}
</script>
