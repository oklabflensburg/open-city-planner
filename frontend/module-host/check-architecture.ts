import { fileURLToPath } from 'node:url'
import { delimiter, resolve } from 'node:path'
import { activeFrontendViolations } from './import-boundaries.ts'

const defaultRepositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const repositoryRoot = process.env.OCP_ARCHITECTURE_ROOT || defaultRepositoryRoot
const frontendRoot = process.env.OCP_ARCHITECTURE_FRONTEND_ROOT
const installedModuleDirectories = (process.env.OCP_INSTALLED_FRONTEND_MODULE_ROOTS || '')
  .split(delimiter)
  .filter(Boolean)

try {
  const localModules = frontendRoot
    ? resolve(frontendRoot, 'frontend-modules')
    : fileURLToPath(new URL('../frontend-modules', import.meta.url))
  const violations = activeFrontendViolations({
    repositoryRoot,
    frontendRoot,
    modulesDirectories: [localModules, ...installedModuleDirectories]
  })
  for (const item of violations) {
    const guidance = item.rule === 'ARCH-FE-HOST-001'
      ? 'Use the contribution registry instead of concrete module knowledge.'
      : 'Use #frontend-module-sdk, #imports or a public contribution contract.'
    const reason = item.reason ? ` (${item.reason})` : ''
    console.error(`::error file=${item.source},line=${item.line},title=${item.rule}::Forbidden dependency ${item.target}${reason}. ${guidance}`)
  }
  if (violations.length) {
    console.error(`Frontend module architecture check failed with ${violations.length} violation(s).`)
    process.exitCode = 1
  } else {
    console.log('Frontend module architecture check passed.')
  }
} catch (error) {
  console.error(`Frontend architecture check configuration error: ${error instanceof Error ? error.message : String(error)}`)
  process.exitCode = 2
}
