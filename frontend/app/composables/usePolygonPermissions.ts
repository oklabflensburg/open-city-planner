import type { Ref } from 'vue'
import type { PolygonEditorDetail } from '~/types/geo'

export function usePolygonPermissions(editor: Ref<PolygonEditorDetail | null>) {
  const authStore = useAuthStore()
  const hasVerwaltungRole = computed(() => (
    !!authStore.user?.is_superuser
    || authStore.user?.roles?.some(role => role.trim().toUpperCase() === 'VERWALTUNG')
  ))

  return {
    canEditPublicFields: computed(() => !!authStore.canWrite && !!editor.value?.can_edit_public_fields),
    canViewVerwaltung: hasVerwaltungRole,
    canEditVerwaltung: computed(() => !!authStore.canWrite && hasVerwaltungRole.value)
  }
}
