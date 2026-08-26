import { fileURLToPath } from 'node:url'
import { activeFrontendViolations } from './import-boundaries.ts'

const defaultRepositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const repositoryRoot = process.env.OCP_ARCHITECTURE_ROOT || defaultRepositoryRoot
const frontendRoot = process.env.OCP_ARCHITECTURE_FRONTEND_ROOT

try {
  const violations = activeFrontendViolations({ repositoryRoot, frontendRoot })
  for (const item of violations) {
    const guidance = item.rule === 'ARCH-FE-HOST-001'
      ? 'Use the contribution registry instead of concrete module knowledge.'
      : 'Use #frontend-module-sdk, #imports or a public contribution contract.'
    console.error(`::error file=${item.source},line=${item.line},title=${item.rule}::Forbidden dependency ${item.target}. ${guidance}`)
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
