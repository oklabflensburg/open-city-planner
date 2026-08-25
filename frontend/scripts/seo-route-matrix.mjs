export const SEO_AUDIT_SITE_ORIGIN = 'https://stadtplaner.example.test'
export const SEO_AUDIT_PUBLIC_API_ORIGIN = 'https://api.stadtplaner.example.test'
export const SEO_AUDIT_AREA_SLUG = 'audit-altstadt'
export const SEO_AUDIT_POLYGON_SLUG = 'audit-testflaeche'

export const DYNAMIC_PUBLIC_ROUTES = [
  {
    path: `/gebiete/${SEO_AUDIT_AREA_SLUG}`,
    previewPath: `/api/v1/analysis-areas/by-slug/${SEO_AUDIT_AREA_SLUG}/preview.webp`
  },
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
  { path: '/flaechen/neu', type: 'auth' },
  { path: '/admin/social', type: 'admin/internal' },
  { path: '/verwaltung/kennzahlen', type: 'admin/internal' }
]

export const SOCIAL_PREVIEW_ROUTES = [
  { path: '/karte?social-preview=1', canonicalPath: '/karte' },
  { path: `/gebiete/${SEO_AUDIT_AREA_SLUG}?social-preview=1&map=0`, canonicalPath: `/gebiete/${SEO_AUDIT_AREA_SLUG}` },
  { path: `/flaechen/${SEO_AUDIT_POLYGON_SLUG}?social-preview=1&map=0`, canonicalPath: `/flaechen/${SEO_AUDIT_POLYGON_SLUG}` }
]

export const NOT_FOUND_ROUTES = [
  '/seo-audit-does-not-exist',
  '/gebiete/seo-audit-does-not-exist',
  '/flaechen/seo-audit-does-not-exist'
]

export const REDIRECT_ROUTES = [
  { path: `/?gebiet=${SEO_AUDIT_AREA_SLUG}`, status: 301, target: `/karte?gebiet=${SEO_AUDIT_AREA_SLUG}` }
]
