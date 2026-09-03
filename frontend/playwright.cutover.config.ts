import { defineConfig } from '@playwright/test'
import hostConfig from './playwright.config'

export default defineConfig({
  ...hostConfig,
  testDir: './e2e-cutover',
  webServer: hostConfig.webServer.map((server, index) => ({
    ...server,
    env: {
      ...server.env,
      ...(index === 0 ? { CORS_ORIGINS: 'http://127.0.0.1:3010' } : {}),
      ...(index === 1 ? { NUXT_PUBLIC_SITE_URL: 'http://127.0.0.1:3010' } : {})
    }
  }))
})
