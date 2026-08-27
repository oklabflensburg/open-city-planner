import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const repositoryFile = (path: string) => readFileSync(fileURLToPath(new URL(`../../${path}`, import.meta.url)), 'utf8')

const environmentKeys = (content: string) => [...content.matchAll(/^([A-Z][A-Z0-9_]*)=/gm)].map(match => match[1]).sort()

const vaultEnvironmentKeys = (vault: string, variable: string) => {
  const marker = `${variable}: |\n`
  const start = vault.indexOf(marker)
  expect(start).toBeGreaterThanOrEqual(0)
  const block = vault.slice(start + marker.length).split('\n')
  const lines = block.slice(0, block.findIndex(line => line && !line.startsWith(' ')))
  return environmentKeys(lines.map(line => line.slice(2)).join('\n'))
}

describe('Ansible deployment contract', () => {
  const vault = repositoryFile('deploy/ansible/vault.example.yml')

  it.each([
    ['stadtplaner_backend_env_content', 'backend/.env.example'],
    ['stadtplaner_frontend_env_content', 'frontend/.env.example'],
    ['stadtplaner_osm_env_content', 'deploy/osm-sync.env.example']
  ])('documents every key from %s', (variable, source) => {
    expect(vaultEnvironmentKeys(vault, variable)).toEqual(environmentKeys(repositoryFile(source)))
  })

  it('documents every overridable Ansible variable', () => {
    const defaults = [
      repositoryFile('deploy/ansible/inventory/group_vars/all.yml'),
      repositoryFile('deploy/ansible/roles/stadtplaner_dns_preflight/defaults/main.yml'),
      repositoryFile('deploy/ansible/roles/stadtplaner_runtime/defaults/main.yml')
    ].join('\n')
    const expected = [...defaults.matchAll(/^(stadtplaner_[a-z0-9_]+):/gm)].map(match => match[1])

    for (const variable of expected)
      expect(vault).toMatch(new RegExp(`^${variable}:`, 'm'))
  })

  it('never exposes backend module settings through Nuxt public runtime config', () => {
    const nuxt = repositoryFile('frontend/nuxt.config.ts')
    const frontendEnvironment = repositoryFile('frontend/.env.example')

    expect(nuxt).not.toContain('OCP_MODULE_')
    expect(nuxt).not.toContain('STADTPLANER_MODULE_ENV_CONFIG')
    expect(frontendEnvironment).not.toContain('OCP_MODULE_')
  })

  it('documents a consistent production module inventory', () => {
    expect(vault).toContain('  ENABLED_MODULES=analysis-areas')
    expect(vault).toContain('  OCP_FRONTEND_MODULES=analysis-areas')
    expect(vault).toContain('  OCP_BACKEND_MODULES=analysis-areas@1.0.0')
  })

  it('runs managed runtime preparation before the application role', () => {
    const deploy = repositoryFile('deploy/ansible/playbooks/deploy.yml')
    expect(deploy.indexOf('role: stadtplaner_dns_preflight')).toBeLessThan(deploy.indexOf('role: stadtplaner_runtime'))
    expect(deploy.indexOf('role: stadtplaner_runtime')).toBeLessThan(deploy.indexOf('role: stadtplaner\n'))
    expect(repositoryFile('deploy/ansible/playbooks/preflight.yml')).toContain('role: stadtplaner_dns_preflight')
  })

  it('validates and publishes a read-only database dump before migrations', () => {
    const tasks = repositoryFile('deploy/ansible/roles/stadtplaner/tasks/main.yml')
    const dump = tasks.indexOf('name: Create managed pre-migration database backup')
    const validate = tasks.indexOf('name: Validate managed database backup archive')
    const publish = tasks.indexOf('name: Publish validated managed database backup atomically')
    const migrate = tasks.indexOf('name: Apply Alembic migrations')

    expect(tasks).toContain('become_user: postgres')
    expect(tasks).toContain('--lock-wait-timeout=30s')
    expect(dump).toBeLessThan(validate)
    expect(validate).toBeLessThan(publish)
    expect(publish).toBeLessThan(migrate)
  })

  it('prepares rollback state and releases ports before activating managed services', () => {
    const tasks = repositoryFile('deploy/ansible/roles/stadtplaner/tasks/main.yml')
    const settings = repositoryFile('backend/app/core/config.py')
    const validateActive = tasks.indexOf('name: Validate the active backend environment against the active release')
    const snapshotPrevious = tasks.indexOf('name: Snapshot legacy active environments for rollback')
    const bindPrevious = tasks.indexOf('name: Bind previous environment snapshots to their release SHA')
    const bindTarget = tasks.indexOf('name: Bind target environment snapshots to the target release SHA')
    const validateTargetFrontend = tasks.indexOf('name: Validate target frontend environment syntax without exposing values')
    const validateModuleInventory = tasks.indexOf('name: Validate backend and frontend module inventories')
    const validateTargetBackend = tasks.indexOf('name: Validate target backend settings before release activation')
    const stopManaged = tasks.indexOf('name: Stop managed primary services before the code and environment switch')
    const freePorts = tasks.indexOf('name: Require application ports to be free before the release switch')
    const activateBackend = tasks.indexOf('name: Activate the target backend environment snapshot')
    const activateFrontend = tasks.indexOf('name: Activate the target frontend environment snapshot')
    const activateCode = tasks.indexOf('name: Switch the active release atomically while services are stopped')
    const startManaged = tasks.indexOf('name: Enable and start primary application services')
    const restoreCode = tasks.indexOf('name: Restore the previous code release link')
    const restoreBackend = tasks.indexOf('name: Restore the previous backend environment link')
    const restoreFrontend = tasks.indexOf('name: Restore the previous frontend environment link')
    const startPrevious = tasks.indexOf('name: Start previous API and frontend releases')

    for (const task of [
      validateActive,
      snapshotPrevious,
      bindPrevious,
      bindTarget,
      validateTargetFrontend,
      validateModuleInventory,
      validateTargetBackend,
      stopManaged,
      freePorts,
      activateBackend,
      activateFrontend,
      activateCode,
      startManaged,
      restoreCode,
      restoreBackend,
      restoreFrontend,
      startPrevious
    ])
      expect(task).toBeGreaterThanOrEqual(0)

    expect(validateActive).toBeLessThan(snapshotPrevious)
    expect(snapshotPrevious).toBeLessThan(bindPrevious)
    expect(bindPrevious).toBeLessThan(stopManaged)
    expect(bindTarget).toBeLessThan(validateTargetFrontend)
    expect(validateTargetFrontend).toBeLessThan(validateModuleInventory)
    expect(validateModuleInventory).toBeLessThan(validateTargetBackend)
    expect(validateTargetFrontend).toBeLessThan(validateTargetBackend)
    expect(validateTargetBackend).toBeLessThan(stopManaged)
    expect(stopManaged).toBeLessThan(freePorts)
    expect(freePorts).toBeLessThan(activateBackend)
    expect(activateBackend).toBeLessThan(activateFrontend)
    expect(activateFrontend).toBeLessThan(activateCode)
    expect(activateCode).toBeLessThan(startManaged)
    expect(restoreCode).toBeLessThan(startPrevious)
    expect(restoreBackend).toBeLessThan(startPrevious)
    expect(restoreFrontend).toBeLessThan(startPrevious)
    expect(freePorts).toBeLessThan(startManaged)
    expect(tasks).toContain('stadtplaner_target_env_dir: "{{ stadtplaner_env_releases_dir }}/{{ stadtplaner_release_sha }}"')
    expect(tasks).toContain('stadtplaner_previous_env_dir: "{{ stadtplaner_env_releases_dir }}/{{ stadtplaner_previous_release_path | basename }}"')
    expect(settings).toContain('extra="forbid"')
    expect(tasks).not.toContain('name: Verify the service user can read persistent environments')
    expect(tasks).not.toContain('name: Stop and disable legacy primary services')
  })

  it('keeps the configured avatar storage writable through systemd hardening', () => {
    const defaults = repositoryFile('deploy/ansible/inventory/group_vars/all.yml')
    const vault = repositoryFile('deploy/ansible/vault.example.yml')
    const tasks = repositoryFile('deploy/ansible/roles/stadtplaner/tasks/main.yml')
    const unit = repositoryFile('deploy/ansible/roles/stadtplaner/templates/stadtplaner-api.service.j2')

    expect(defaults).toContain('stadtplaner_avatar_upload_dir: /data/uploads')
    expect(vault).toContain('AVATAR_UPLOAD_DIR=/data/uploads')
    expect(tasks).toContain('{{ stadtplaner_avatar_upload_dir }}/avatars')
    expect(unit).toContain('ReadWritePaths=')
    expect(unit).toContain('{{ stadtplaner_avatar_upload_dir }}')
  })

  it('allows avatar uploads through the managed API vhost', () => {
    const nginx = repositoryFile('deploy/ansible/roles/stadtplaner/templates/stadtplaner.nginx.conf.j2')

    expect(nginx).toMatch(/server_name \{\{ stadtplaner_api_host \}\};\s+client_max_body_size 10m;/)
  })

  it('deploys the exact main commit without weakening SSH verification', () => {
    const workflow = repositoryFile('.github/workflows/deploy.yml')

    expect(workflow).toContain('environment:\n      name: production')
    expect(workflow).toContain('cancel-in-progress: false')
    expect(workflow).toContain('github.event.workflow_run.conclusion == \'success\'')
    expect(workflow).toContain('ANSIBLE_HOST_KEY_CHECKING: "True"')
    expect(workflow).toContain('secrets.STADTPLANER_ANSIBLE_REMOTE_USER')
    expect(workflow).toContain('STADTPLANER_SSH_KNOWN_HOSTS')
    expect(workflow).toContain('vars.STADTPLANER_BACKEND_ENV_CONFIG')
    expect(workflow).toContain('secrets.STADTPLANER_MODULE_ENV_CONFIG')
    expect(workflow).toContain('secrets.STADTPLANER_DATABASE_URL')
    expect(workflow).toContain('stadtplaner_deploy_ref=${STADTPLANER_DEPLOY_SHA}')
    expect(workflow.match(/--become-password-file/g)).toHaveLength(2)
    expect(workflow).not.toContain('STADTPLANER_ANSIBLE_VAULT_BASE64')
    expect(workflow).not.toContain('--vault-password-file')
    expect(workflow).not.toContain('StrictHostKeyChecking=no')
  })
})
