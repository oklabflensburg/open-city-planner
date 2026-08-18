<template>
  <Button
    class="w-full max-w-full sm:w-auto sm:min-w-52"
    type="button"
    :active="following"
    :aria-pressed="following"
    :aria-busy="pending"
    :disabled="pending"
    @click="toggle"
  >
    <BellRing v-if="following" class="size-4 shrink-0" aria-hidden="true" />
    <BellPlus v-else class="size-4 shrink-0" aria-hidden="true" />
    <span class="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)] text-center leading-5">
      <span class="invisible col-start-1 row-start-1 whitespace-normal [overflow-wrap:anywhere]" aria-hidden="true">{{ followLabel }}</span>
      <span class="invisible col-start-1 row-start-1 whitespace-normal [overflow-wrap:anywhere]" aria-hidden="true">{{ followedLabel }}</span>
      <span class="col-start-1 row-start-1 whitespace-normal [overflow-wrap:anywhere]">{{ pending ? 'Wird geladen …' : following ? followedLabel : followLabel }}</span>
    </span>
  </Button>
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
const pending = computed(() => loading.value || !store.subscriptionsLoaded)

async function toggle() {
  if (pending.value) return
  loading.value = true
  try {
    if (following.value) await store.unfollow(props.resourceType, props.resourceId)
    else await store.follow(props.resourceType, props.resourceId)
    store.showToast({ title: following.value ? 'Benachrichtigungen aktiviert' : 'Benachrichtigungen deaktiviert', priority: 'SUCCESS' })
  } catch (error) {
    store.showToast({
      title: following.value ? 'Folgen konnte nicht beendet werden' : 'Folgen konnte nicht aktiviert werden',
      message: error instanceof Error ? error.message : undefined,
      priority: 'ERROR'
    })
  } finally {
    loading.value = false
  }
}
</script>
