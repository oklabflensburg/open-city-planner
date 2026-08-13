import { z } from 'zod'

export const contactFormSchema = z.object({
  name: z.string().trim().min(2, 'Bitte geben Sie mindestens 2 Zeichen ein.').max(120, 'Der Name darf höchstens 120 Zeichen enthalten.'),
  email: z.string().trim().max(320, 'Die E-Mail-Adresse ist zu lang.').email('Bitte geben Sie eine gültige E-Mail-Adresse ein.'),
  subject: z.string().trim().min(3, 'Bitte geben Sie mindestens 3 Zeichen ein.').max(160, 'Der Betreff darf höchstens 160 Zeichen enthalten.'),
  message: z.string().trim().min(10, 'Bitte geben Sie mindestens 10 Zeichen ein.').max(5000, 'Die Nachricht darf höchstens 5000 Zeichen enthalten.')
})

export type ContactFormFields = z.infer<typeof contactFormSchema>

export function contactFieldErrors(fields: ContactFormFields) {
  const result = contactFormSchema.safeParse(fields)
  if (result.success) return {}
  return Object.fromEntries(
    Object.entries(result.error.flatten().fieldErrors).map(([field, messages]) => [field, messages?.[0] || 'Ungültige Eingabe.'])
  ) as Partial<Record<keyof ContactFormFields, string>>
}
