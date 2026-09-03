import { defineConfig } from '@playwright/test'
import hostConfig from './playwright.config'

export default defineConfig({
  ...hostConfig,
  testDir: './e2e-cutover'
})
