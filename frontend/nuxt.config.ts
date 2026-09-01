import tailwindcss from '@tailwindcss/vite'

const configuredSiteUrl = process.env.NUXT_PUBLIC_SITE_URL
const configuredMapStyleUrl = process.env.NUXT_PUBLIC_MAP_STYLE_URL || process.env.NUXT_PUBLIC_VERSATILES_STYLE_URL || ''
const effectiveMapStyleUrl = configuredMapStyleUrl.includes('/assets/styles/colorful/style.json') ? '' : configuredMapStyleUrl
const apiOrigin = (() => {
  try { return new URL(process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1').origin } catch { return '' }
})()
const mapOrigin = (() => {
  try { return effectiveMapStyleUrl ? new URL(effectiveMapStyleUrl).origin : 'https://tiles.versatiles.org' } catch { return '' }
})()
const securityHeaders = {
  'content-security-policy': [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com https://plausible.oklabflensburg.de",
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: https: ${apiOrigin}`.trim(),
    // ws:/wss: are needed by Nuxt HMR and deployments that expose realtime transports.
    `connect-src 'self' ws: wss: ${apiOrigin} ${mapOrigin} https://plausible.oklabflensburg.de`.trim(),
    `font-src 'self' data: ${mapOrigin}`.trim(),
    "worker-src 'self' blob:",
    "frame-src https://challenges.cloudflare.com"
  ].join('; '),
  'referrer-policy': 'strict-origin-when-cross-origin',
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'permissions-policy': 'geolocation=(), microphone=(), camera=(), publickey-credentials-create=(self), publickey-credentials-get=(self)',
  'cross-origin-opener-policy': 'same-origin',
  'cross-origin-resource-policy': 'same-site',
  ...(process.env.NODE_ENV === 'production'
    ? { 'strict-transport-security': 'max-age=31536000; includeSubDomains' }
    : {})
}
if (process.env.NODE_ENV === 'production' && !configuredSiteUrl) {
  console.warn('NUXT_PUBLIC_SITE_URL is not set; canonical URLs will use the local fallback.')
}
if (configuredMapStyleUrl && !effectiveMapStyleUrl) {
  console.warn('The heavyweight VersaTiles colorful style is disabled; using the local stadtplaner-light style.')
}

export default defineNuxtConfig({
  compatibilityDate: '2026-08-10',
  features: {
    devLogs: false
  },
  experimental: {
    defaults: {
      nuxtLink: {
        prefetchOn: { visibility: false, interaction: true }
      }
    }
  },
  modules: ['@pinia/nuxt'],
  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    environment: process.env.APP_ENVIRONMENT || process.env.NODE_ENV || 'development',
    releaseSha: process.env.STADTPLANER_RELEASE_SHA || 'dev',
    apiInternalBaseUrl: process.env.NUXT_API_INTERNAL_BASE_URL || '',
    public: {
      siteName: 'OK Lab Flensburg',
      siteUrl: configuredSiteUrl || 'http://localhost:3000',
      siteLocale: 'de_DE',
      defaultSeoTitle: 'Interaktive Stadtkarte',
      defaultSeoDescription: 'Interaktive GIS-Karte für Verkaufsflächen, offene Daten und Stadtanalyse in Flensburg.',
      defaultOgImage: process.env.NUXT_PUBLIC_DEFAULT_OG_IMAGE || '/branding/stadtplaner-social-card.png',
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1',
      mediaBaseUrl: process.env.NUXT_PUBLIC_MEDIA_BASE_URL || '',
      avatarMaxUploadBytes: Number(process.env.NUXT_PUBLIC_AVATAR_MAX_UPLOAD_BYTES || 5242880),
      mapStyleUrl: effectiveMapStyleUrl,
      mapCenterLng: Number(process.env.NUXT_PUBLIC_MAP_CENTER_LNG || 9.435),
      mapCenterLat: Number(process.env.NUXT_PUBLIC_MAP_CENTER_LAT || 54.783),
      mapZoom: Number(process.env.NUXT_PUBLIC_MAP_ZOOM || 16.4),
      mapPerformanceDebug: process.env.NUXT_PUBLIC_MAP_PERFORMANCE_DEBUG === 'true',
      contactMail: process.env.NUXT_PUBLIC_CONTACT_MAIL || 'oklabflensburg@grain.one',
      contactPhone: process.env.NUXT_PUBLIC_CONTACT_PHONE || '+49 176 59978074',
      privacyContactPerson: process.env.NUXT_PUBLIC_PRIVACY_CONTACT_PERSON || '',
      addressName: process.env.NUXT_PUBLIC_ADDRESS_NAME || 'Open Knowledge Lab Flensburg',
      addressStreet: process.env.NUXT_PUBLIC_ADDRESS_STREET || 'Am Nordertor',
      addressHouseNumber: process.env.NUXT_PUBLIC_ADDRESS_HOUSE_NUMBER || '2',
      addressPostalCode: process.env.NUXT_PUBLIC_ADDRESS_POSTAL_CODE || '24939',
      addressCity: process.env.NUXT_PUBLIC_ADDRESS_CITY || 'Flensburg',
      websiteOrigin: process.env.NUXT_PUBLIC_WEBSITE_ORIGIN || ''
    }
  },
  app: {
    head: {
      htmlAttrs: { lang: 'de' },
      meta: [
        { name: 'theme-color', content: '#154d73' },
        { name: 'twitter:site', content: '@oklabflensburg' }
      ],
      link: [
        { rel: 'icon', href: '/favicon.ico' },
        { rel: 'icon', type: 'image/svg+xml', href: '/branding/ok-lab-flensburg.svg' },
        { rel: 'icon', type: 'image/png', sizes: '96x96', href: '/favicon-96x96.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
        { rel: 'manifest', href: '/site.webmanifest' }
      ],
      script: [
        {
          async: true,
          src: 'https://plausible.oklabflensburg.de/js/pa-Eke2bW8oyDVoFdCqvfZ7f.js'
        },
        {
          innerHTML: 'window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},plausible.init=plausible.init||function(i){plausible.o=i||{}}; plausible.init()'
        }
      ]
    }
  },
  nitro: {
    compressPublicAssets: true,
    routeRules: {
      '/**': { headers: securityHeaders },
      '/_nuxt/**': { headers: { 'cache-control': 'public, max-age=31536000, immutable' } },
      '/branding/**': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/favicon.ico': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/favicon-96x96.png': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/apple-touch-icon.png': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/web-app-manifest-192x192.png': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/web-app-manifest-512x512.png': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/site.webmanifest': { headers: { 'cache-control': 'public, max-age=86400' } },
      '/map-styles/**': { headers: { 'cache-control': 'public, max-age=86400' } }
    }
  },
  typescript: {
    strict: true
  },
  vite: {
    plugins: [tailwindcss()],
    optimizeDeps: {
      exclude: ['terra-draw', 'terra-draw-maplibre-gl-adapter']
    }
  }
})
