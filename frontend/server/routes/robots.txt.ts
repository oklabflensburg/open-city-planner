import { buildAbsoluteUrl } from '~/utils/seo'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  setResponseHeader(event, 'content-type', 'text/plain; charset=utf-8')
  return [
    'User-agent: *',
    'Allow: /',
    'Disallow: /login',
    'Disallow: /registrieren',
    'Disallow: /profil',
    'Disallow: /meine-flaechen',
    'Disallow: /flaechen/neu/',
    'Disallow: /passwort-',
    'Disallow: /email-bestaetigen',
    'Disallow: /email-abmelden',
    'Disallow: /auth/',
    'Disallow: /admin/',
    'Disallow: /verwaltung/',
    `Sitemap: ${buildAbsoluteUrl(config.public.siteUrl, '/sitemap.xml')}`,
    ''
  ].join('\n')
})
