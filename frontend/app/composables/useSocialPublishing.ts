import type { MastodonAdminStatus, SocialPublicationItem, SocialPublicationPage, SocialPublicationPreview, SocialPublicationStatus, SocialPublishingSettings, SocialPublishingSettingsPatch } from '~/types/admin'
import { createSerialSaveQueue, type SerialSaveState } from '~/utils/serialSaveQueue'

export function useSocialPublishing() {
  const { request } = useApi()
  const mastodonStatus = ref<MastodonAdminStatus | null>(null)
  const settings = ref<SocialPublishingSettings | null>(null)
  const items = ref<SocialPublicationItem[]>([])
  const total = ref(0)
  const pages = ref(1)
  const page = ref(1)
  const pageSize = 25
  const publicationStatus = ref<SocialPublicationStatus | ''>('')
  const loading = ref(false)
  const error = ref('')
  const retryingId = ref('')
  const settingsSaveStatus = ref<SerialSaveState>('saved')
  const settingsSaveError = ref('')
  const actingId = ref('')
  const settingsQueue = createSerialSaveQueue<SocialPublishingSettingsPatch, SocialPublishingSettings>({
    save: patch => request<SocialPublishingSettings>('/admin/social/settings', {
      method: 'PATCH',
      body: JSON.stringify(patch)
    }),
    onSaved: result => {
      settings.value = result
      settingsSaveError.value = ''
    },
    onStateChange: (state, caught) => {
      settingsSaveStatus.value = state
      if (state === 'error') {
        settingsSaveError.value = caught instanceof Error ? caught.message : 'Änderungen konnten nicht gespeichert werden.'
      } else if (state === 'saving') {
        settingsSaveError.value = ''
      }
    }
  })
  const savingSettings = computed(() => settingsSaveStatus.value === 'saving')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const query = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) })
      if (publicationStatus.value) query.set('status', publicationStatus.value)
      const [statusResult, settingsResult, publications] = await Promise.all([
        request<MastodonAdminStatus>('/admin/social/mastodon/status'),
        request<SocialPublishingSettings>('/admin/social/settings'),
        request<SocialPublicationPage>(`/admin/social/publications?${query}`)
      ])
      mastodonStatus.value = statusResult
      settings.value = settingsResult
      items.value = publications.items
      total.value = publications.total
      pages.value = publications.pages
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Social Publishing konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function retry(item: SocialPublicationItem) {
    retryingId.value = item.id
    try {
      await request(`/admin/social/publications/${item.id}/retry`, { method: 'POST' })
      await load()
    } finally {
      retryingId.value = ''
    }
  }

  function saveSettingsPatch(patch: SocialPublishingSettingsPatch) { settingsQueue.enqueue(patch) }
  function retrySettingsSave() { settingsQueue.retry() }
  async function flushSettingsSaves() { await settingsQueue.flush() }

  async function preview(item: SocialPublicationItem) {
    return await request<SocialPublicationPreview>(`/admin/social/publications/${item.id}/preview`)
  }

  async function action(item: SocialPublicationItem, name: 'approve-and-publish' | 'cancel', altText?: string) {
    actingId.value = item.id
    try {
      await request(`/admin/social/publications/${item.id}/${name}`, {
        method: 'POST',
        ...(name === 'approve-and-publish' ? { body: JSON.stringify({ alt_text: altText }) } : {})
      })
      await load()
    } finally { actingId.value = '' }
  }

  return {
    mastodonStatus, settings, items, total, pages, page, publicationStatus, loading, error,
    retryingId, savingSettings, settingsSaveStatus, settingsSaveError, actingId,
    load, retry, saveSettingsPatch, retrySettingsSave, flushSettingsSaves,
    preview, action
  }
}
