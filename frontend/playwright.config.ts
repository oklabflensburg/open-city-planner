import { existsSync } from 'node:fs'
import { defineConfig, devices } from '@playwright/test'

const localBackendPython = process.platform === 'win32'
  ? '../backend/.venv/Scripts/python.exe'
  : '../backend/.venv/bin/python'
const backendPython = process.env.PLAYWRIGHT_BACKEND_PYTHON
  || (existsSync(localBackendPython) ? localBackendPython : 'python')
const chromiumPath = process.env.PLAYWRIGHT_CHROMIUM_PATH

export default defineConfig({
  testDir: './e2e',
  fullyParallel: !process.env.CI,
  workers: process.env.CI ? 1 : undefined,
  retries: 0,
  reporter: process.env.CI
    ? [['line'], ['html', { open: 'never' }]]
    : 'line',
  use: {
    baseURL: 'http://127.0.0.1:3010',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
    launchOptions: chromiumPath ? { executablePath: chromiumPath } : undefined
  },
  webServer: [
    {
      command: `${backendPython} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8010`,
      url: 'http://127.0.0.1:8010/health',
      env: {
        AUTH_RATE_LIMIT_ATTEMPTS: '500',
        JWT_ISSUER: 'http://127.0.0.1:8010',
        JWT_SECRET_KEY: 'playwright-e2e-jwt-signing-key-32-bytes'
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000
    },
    {
      command: 'NUXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api/v1 pnpm dev --host 127.0.0.1 --port 3010',
      url: 'http://127.0.0.1:3010',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000
    }
  ]
})
