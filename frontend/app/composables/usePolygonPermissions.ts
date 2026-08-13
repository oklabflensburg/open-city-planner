import type { Ref } from 'vue'
import type { PolygonEditorDetail } from '~/types/geo'
import { hasVerwaltungRole } from '~/utils/roles'

export function usePolygonPermissions(editor: Ref<PolygonEditorDetail | null>) {
  const authStore = useAuthStore()
  const hasVerwaltung = computed(() => hasVerwaltungRole(authStore.user))

  return {
    canEditPublicFields: computed(() => !!authStore.canWrite && !!editor.value?.can_edit_public_fields),
    canDelete: computed(() => !!authStore.authenticated && !!editor.value?.can_delete),
    canViewVerwaltung: hasVerwaltung,
    canEditVerwaltung: computed(() => !!authStore.canWrite && hasVerwaltung.value)
  }
}
