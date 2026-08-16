import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:3010',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || '/snap/bin/chromium' }
  },
  webServer: [
    {
      command: 'MASTODON_ENABLED=false ../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8010',
      url: 'http://127.0.0.1:8010/health',
      reuseExistingServer: true,
      timeout: 120_000
    },
    {
      command: 'NUXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api/v1 pnpm dev --host 127.0.0.1 --port 3010',
      url: 'http://127.0.0.1:3010',
      reuseExistingServer: true,
      timeout: 120_000
    }
  ]
})
