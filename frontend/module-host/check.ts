import { fileURLToPath } from 'node:url'
import { resolveFrontendModules } from './discovery.ts'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const modules = resolveFrontendModules({
  modulesDirectory: fileURLToPath(new URL('../frontend-modules', import.meta.url)),
  appPagesDirectory: fileURLToPath(new URL('../app/pages', import.meta.url)),
  enabledModules: process.env.OCP_FRONTEND_MODULES,
  backendModules: process.env.OCP_BACKEND_MODULES
})

console.log(`Frontend module preflight passed: ${modules.map(module => module.id).join(', ') || 'no optional modules enabled'}.`)
