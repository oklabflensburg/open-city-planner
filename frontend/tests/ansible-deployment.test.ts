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

  it('releases the application ports before starting managed services', () => {
    const tasks = repositoryFile('deploy/ansible/roles/stadtplaner/tasks/main.yml')
    const readable = tasks.indexOf('name: Verify the service user can read persistent environments')
    const stopManaged = tasks.indexOf('name: Stop managed primary services before legacy handover')
    const freePorts = tasks.indexOf('name: Require application ports to be free after legacy handover')
    const startManaged = tasks.indexOf('name: Enable and start primary application services')

    expect(readable).toBeGreaterThanOrEqual(0)
    expect(stopManaged).toBeLessThan(freePorts)
    expect(freePorts).toBeLessThan(startManaged)
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
    expect(workflow).toContain('secrets.STADTPLANER_DATABASE_URL')
    expect(workflow).toContain('stadtplaner_deploy_ref=${STADTPLANER_DEPLOY_SHA}')
    expect(workflow.match(/--become-password-file/g)).toHaveLength(2)
    expect(workflow).not.toContain('STADTPLANER_ANSIBLE_VAULT_BASE64')
    expect(workflow).not.toContain('--vault-password-file')
    expect(workflow).not.toContain('StrictHostKeyChecking=no')
  })
})
