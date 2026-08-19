import type { EmailCampaign, EmailCampaignPreview, EmailCampaignWrite } from '~/types/admin'

export function useEmailCampaigns() {
  const { request } = useApi()
  const base = '/admin/email-campaigns'
  return {
    list: () => request<EmailCampaign[]>(base),
    load: (id: string) => request<EmailCampaign>(`${base}/${id}`),
    create: (payload: Omit<EmailCampaignWrite, 'version'> & { version?: number }) => request<EmailCampaign>(base, { method: 'POST', body: JSON.stringify(payload) }),
    save: (item: EmailCampaign) => request<EmailCampaign>(`${base}/${item.id}`, { method: 'PATCH', body: JSON.stringify(item) }),
    preview: (id: string) => request<EmailCampaignPreview>(`${base}/${id}/preview`, { method: 'POST' }),
    testSend: (id: string) => request<{ message: string }>(`${base}/${id}/test-send`, { method: 'POST' }),
    recipientCount: (id: string) => request<{ recipient_count: number }>(`${base}/${id}/recipient-count`),
    start: (id: string, legalConfirmed: boolean) => request<EmailCampaign>(`${base}/${id}/start`, { method: 'POST', body: JSON.stringify({ legal_confirmed: legalConfirmed }) }),
    cancel: (id: string) => request<EmailCampaign>(`${base}/${id}/cancel`, { method: 'POST' })
  }
}
