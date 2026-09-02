export const SEO_AUDIT_SITE_ORIGIN = 'https://stadtplaner.example.test'
export const SEO_AUDIT_PUBLIC_API_ORIGIN = 'https://api.stadtplaner.example.test'
export const SEO_AUDIT_POLYGON_SLUG = 'audit-testflaeche'

export const DYNAMIC_PUBLIC_ROUTES = [
  {
    path: `/flaechen/${SEO_AUDIT_POLYGON_SLUG}`,
    previewPath: `/api/v1/polygons/by-slug/${SEO_AUDIT_POLYGON_SLUG}/preview.webp`
  }
]

export const NOINDEX_ROUTES = [
  { path: '/impressum', type: 'public-noindex', robots: 'noindex,follow' },
  { path: '/datenschutz', type: 'public-noindex', robots: 'noindex,follow' },
  { path: '/login', type: 'public-noindex' },
  { path: '/registrieren', type: 'public-noindex' },
  { path: '/passwort-vergessen', type: 'public-noindex' },
  { path: '/passwort-zuruecksetzen', type: 'public-noindex' },
  { path: '/email-bestaetigen', type: 'public-noindex' },
  { path: '/email-abmelden', type: 'public-noindex' },
  { path: '/auth/callback', type: 'auth' },
  { path: '/auth/mfa', type: 'auth' },
  { path: '/profil', type: 'auth' },
  { path: '/meine-flaechen', type: 'auth' },
  { path: '/flaechen/neu', type: 'auth' }
]

export const NOT_FOUND_ROUTES = [
  '/seo-audit-does-not-exist',
  '/flaechen/seo-audit-does-not-exist'
]

export const REDIRECT_ROUTES = [
  { path: '/?polygon=seo-audit-does-not-exist', status: 301, target: '/karte?polygon=seo-audit-does-not-exist' }
]
