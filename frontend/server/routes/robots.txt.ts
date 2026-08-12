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
    'Disallow: /passwort-',
    'Disallow: /auth/',
    `Sitemap: ${buildAbsoluteUrl(config.public.siteUrl, '/sitemap.xml')}`,
    ''
  ].join('\n')
})
