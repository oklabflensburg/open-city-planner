import type { EmailTemplateDetail, EmailTemplateListItem, EmailTemplatePreview } from '~/types/admin'

export function useEmailTemplates() {
  const { request } = useApi()

  async function list() {
    return await request<EmailTemplateListItem[]>('/admin/email-templates')
  }

  async function load(key: string) {
    return await request<EmailTemplateDetail>(`/admin/email-templates/${encodeURIComponent(key)}`)
  }

  function payload(template: EmailTemplateDetail) {
    return {
      subject: template.subject,
      html_body: template.html_body,
      text_body: template.text_body,
      version: template.version
    }
  }

  async function save(template: EmailTemplateDetail) {
    return await request<EmailTemplateDetail>(
      `/admin/email-templates/${encodeURIComponent(template.key)}`,
      { method: 'PATCH', body: JSON.stringify(payload(template)) }
    )
  }

  async function preview(template: EmailTemplateDetail) {
    return await request<EmailTemplatePreview>(
      `/admin/email-templates/${encodeURIComponent(template.key)}/preview`,
      { method: 'POST', body: JSON.stringify(payload(template)) }
    )
  }

  async function testSend(template: EmailTemplateDetail) {
    return await request<{ message: string }>(
      `/admin/email-templates/${encodeURIComponent(template.key)}/test-send`,
      { method: 'POST', body: JSON.stringify(payload(template)) }
    )
  }

  async function reset(template: EmailTemplateDetail) {
    return await request<EmailTemplateDetail>(
      `/admin/email-templates/${encodeURIComponent(template.key)}/reset`,
      { method: 'POST', body: JSON.stringify({ version: template.version }) }
    )
  }

  return { list, load, save, preview, testSend, reset }
}
