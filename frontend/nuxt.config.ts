import tailwindcss from '@tailwindcss/vite'

const configuredSiteUrl = process.env.NUXT_PUBLIC_SITE_URL
if (process.env.NODE_ENV === 'production' && !configuredSiteUrl) {
  console.warn('NUXT_PUBLIC_SITE_URL is not set; canonical URLs will use the local fallback.')
}

export default defineNuxtConfig({
  compatibilityDate: '2026-08-10',
  features: {
    devLogs: false
  },
  modules: ['@pinia/nuxt'],
  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],
  css: ['maplibre-gl/dist/maplibre-gl.css', '~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      siteName: 'OK Lab Flensburg',
      siteUrl: configuredSiteUrl || 'http://localhost:3000',
      siteLocale: 'de_DE',
      defaultSeoTitle: 'Interaktive Stadtkarte',
      defaultSeoDescription: 'Interaktive GIS-Karte für Verkaufsflächen, offene Daten und Stadtanalyse in Flensburg.',
      defaultOgImage: process.env.NUXT_PUBLIC_DEFAULT_OG_IMAGE || '',
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1',
      mediaBaseUrl: process.env.NUXT_PUBLIC_MEDIA_BASE_URL || '',
      avatarMaxUploadBytes: Number(process.env.NUXT_PUBLIC_AVATAR_MAX_UPLOAD_BYTES || 5242880),
      mapStyleUrl: process.env.NUXT_PUBLIC_MAP_STYLE_URL || process.env.NUXT_PUBLIC_VERSATILES_STYLE_URL || '',
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
      link: [{ rel: 'shortcut icon', href: '/favicon.ico' }]
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
