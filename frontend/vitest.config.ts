import { fileURLToPath } from 'node:url'
import { configDefaults, defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: {
    alias: {
      '~': fileURLToPath(new URL('./app', import.meta.url)),
      '#frontend-module-sdk': fileURLToPath(new URL('./module-host/public.ts', import.meta.url))
    }
  },
  test: {
    environment: 'node',
    globals: true,
    exclude: [
      ...configDefaults.exclude,
      'e2e/**',
      'tests/frontend-module-enabled-ssr.test.ts'
    ]
  }
})
