import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { contactFieldErrors, contactFormSchema } from '../app/utils/contact'

const page = readFileSync(fileURLToPath(new URL('../app/pages/kontakt.vue', import.meta.url)), 'utf8')

describe('contact form', () => {
  it('validates all required fields and accepts a valid message', () => {
    expect(contactFormSchema.safeParse({ name: '', email: '', subject: '', message: '' }).success).toBe(false)
    expect(contactFieldErrors({ name: 'Erika', email: 'ungueltig', subject: 'Hinweis', message: 'Eine ausreichend lange Nachricht.' }).email).toContain('gültige')
    expect(contactFormSchema.safeParse({ name: 'Erika', email: 'erika@example.org', subject: 'Hinweis', message: 'Eine ausreichend lange Nachricht.' }).success).toBe(true)
  })

  it('renders accessible bounded fields and the honeypot', () => {
    expect(page).toContain('for="contact-name"')
    expect(page).toContain('autocomplete="email"')
    expect(page).toContain(':aria-invalid="!!errors.email"')
    expect(page).toContain('maxlength="5000"')
    expect(page).toContain('class="contact-honeypot"')
    expect(page).toContain('website: website.value')
  })

  it('prevents duplicate submits and exposes the loading state', () => {
    expect(page).toContain('if (submitting.value) return')
    expect(page).toContain(':disabled="submitting || tokenLoading')
    expect(page).toContain("submitting ? 'Wird gesendet …' : 'Nachricht senden'")
  })

  it('shows success, preserves fields on errors and maps rate limits', () => {
    expect(page).toContain('Nachricht gesendet')
    expect(page).toContain("CONTACT_RATE_LIMITED: 'Zu viele Nachrichten")
    const catchBlock = page.slice(page.indexOf('} catch (cause)'), page.indexOf('} finally'))
    expect(catchBlock).not.toContain("Object.assign(fields, { name: ''")
  })

  it('links privacy information and keeps public SEO', () => {
    expect(page).toContain('to="/datenschutz"')
    expect(page).toContain("path: '/kontakt'")
    expect(page).toContain('buildWebPageStructuredData')
    expect(page).toContain('Sie erhalten automatisch eine Kopie')
  })

  it('loads optional Turnstile only when enabled by the backend', () => {
    expect(page).toContain('v-if="turnstileEnabled && turnstileSiteKey"')
    expect(page).toContain("request<ContactTokenResponse>('/contact/form-token'")
    expect(page).toContain('turnstile_token: turnstileToken.value || null')
  })
})
