import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { access } from 'node:fs/promises'
import {
  auditIndexableHtml,
  auditNoindexHtml,
  auditNotFoundHtml,
  hasLocalHost,
  parseHtmlSeo,
  robotsDisallowPaths,
  sitemapLocations
} from './seo-audit-lib.mjs'
import { startSeoAuditFixtureApi } from './seo-audit-fixture-api.mjs'
import {
  DYNAMIC_PUBLIC_ROUTES,
  NOINDEX_ROUTES,
  NOT_FOUND_ROUTES,
  REDIRECT_ROUTES,
  SEO_AUDIT_PUBLIC_API_ORIGIN,
  SEO_AUDIT_SITE_ORIGIN
} from './seo-route-matrix.mjs'

const outputEntry = new URL('../.output/server/index.mjs', import.meta.url)
const failures = []
let fixture
let frontend

try {
  await access(outputEntry)
  fixture = await startSeoAuditFixtureApi()
  const port = await availablePort()
  frontend = startFrontend(port, fixture.baseUrl)
  const baseUrl = `http://127.0.0.1:${port}`
  await waitForServer(baseUrl, frontend)
  await auditApplication(baseUrl)
} catch (error) {
  failures.push(`audit: ${error instanceof Error ? error.message : String(error)}`)
} finally {
  if (frontend && frontend.exitCode === null) frontend.kill('SIGTERM')
  if (fixture) await fixture.close()
}

if (failures.length) {
  console.error(`SEO audit failed with ${failures.length} violation${failures.length === 1 ? '' : 's'}:`)
  for (const failure of failures) console.error(`- ${failure}`)
  process.exitCode = 1
} else {
  console.log('SEO audit passed: production SSR, sitemap, robots, noindex, redirects and 404 routes are valid.')
}

async function auditApplication(baseUrl) {
  await auditTechnicalAssets(baseUrl)
  const metadataOwners = { titles: new Map(), descriptions: new Map() }
  const sitemapResponse = await fetch(`${baseUrl}/sitemap.xml`)
  if (sitemapResponse.status !== 200) {
    fail('/sitemap.xml', `expected HTTP 200, received ${sitemapResponse.status}`)
    return
  }
  const sitemapXml = await sitemapResponse.text()
  const locations = sitemapLocations(sitemapXml)
  if (!locations.length) fail('/sitemap.xml', 'contains no URLs')
  if (new Set(locations).size !== locations.length) fail('/sitemap.xml', 'contains duplicate URLs')

  for (const dynamic of DYNAMIC_PUBLIC_ROUTES) {
    if (!locations.includes(`${SEO_AUDIT_SITE_ORIGIN}${dynamic.path}`)) {
      fail('/sitemap.xml', `missing dynamic fixture ${dynamic.path}`)
    }
  }

  const robotsResponse = await fetch(`${baseUrl}/robots.txt`)
  if (robotsResponse.status !== 200) fail('/robots.txt', `expected HTTP 200, received ${robotsResponse.status}`)
  const robots = await robotsResponse.text()
  const expectedSitemap = `Sitemap: ${SEO_AUDIT_SITE_ORIGIN}/sitemap.xml`
  if (!robots.includes(expectedSitemap)) fail('/robots.txt', `missing ${expectedSitemap}`)
  const disallowed = robotsDisallowPaths(robots)

  for (const location of locations) {
    let publicUrl
    try { publicUrl = new URL(location) } catch { fail('/sitemap.xml', `invalid URL ${location}`); continue }
    if (publicUrl.origin !== SEO_AUDIT_SITE_ORIGIN) fail('/sitemap.xml', `unexpected origin in ${location}`)
    if (publicUrl.search) fail('/sitemap.xml', `query parameters in ${location}`)
    if (hasLocalHost(location)) fail('/sitemap.xml', `local host in ${location}`)
    if (disallowed.some(rule => publicUrl.pathname.startsWith(rule))) fail('/robots.txt', `blocks sitemap route ${publicUrl.pathname}`)

    const response = await fetch(`${baseUrl}${publicUrl.pathname}`, { redirect: 'manual' })
    if (response.status !== 200) {
      fail(publicUrl.pathname, `expected HTTP 200 from sitemap, received ${response.status}`)
      continue
    }
    const html = await response.text()
    const dynamic = DYNAMIC_PUBLIC_ROUTES.find(item => item.path === publicUrl.pathname)
    report(publicUrl.pathname, auditIndexableHtml(html, {
      expectedUrl: location,
      expectSocialImage: true
    }))
    auditUniqueMetadata(publicUrl.pathname, html, metadataOwners)
    if (dynamic) auditDynamicSocialImage(publicUrl.pathname, html, dynamic.previewPath)
    else auditDefaultSocialImage(publicUrl.pathname, html)
  }

  for (const route of NOINDEX_ROUTES) {
    const response = await fetch(`${baseUrl}${route.path}`, { redirect: 'manual' })
    if (response.status !== 200) fail(route.path, `expected HTTP 200 for ${route.type}, received ${response.status}`)
    else report(route.path, auditNoindexHtml(await response.text(), {
      expectedRobots: route.robots || 'noindex,nofollow'
    }))
    if (locations.includes(`${SEO_AUDIT_SITE_ORIGIN}${route.path}`)) fail('/sitemap.xml', `contains ${route.type} route ${route.path}`)
  }

  for (const path of NOT_FOUND_ROUTES) {
    const response = await fetch(`${baseUrl}${path}`, {
      redirect: 'manual',
      headers: { Accept: 'text/html' }
    })
    if (response.status !== 404) fail(path, `expected HTTP 404, received ${response.status}`)
    report(path, auditNotFoundHtml(await response.text()))
  }

  for (const route of REDIRECT_ROUTES) {
    const response = await fetch(`${baseUrl}${route.path}`, { redirect: 'manual' })
    if (response.status !== route.status) fail(route.path, `expected HTTP ${route.status}, received ${response.status}`)
    const location = response.headers.get('location')
    if (!location) { fail(route.path, 'redirect is missing Location'); continue }
    const target = new URL(location, SEO_AUDIT_SITE_ORIGIN)
    if (`${target.pathname}${target.search}` !== route.target) fail(route.path, `redirect target is ${target.pathname}${target.search}, expected ${route.target}`)
    const targetResponse = await fetch(`${baseUrl}${route.target}`, { redirect: 'manual' })
    if (targetResponse.status >= 300 && targetResponse.status < 400) fail(route.path, 'redirect target starts another redirect')
  }
}

function auditUniqueMetadata(path, html, owners) {
  const page = parseHtmlSeo(html)
  const title = page.titles[0]
  const description = page.meta.find(item => item.name === 'description')?.content
  for (const [kind, value, entries] of [
    ['title', title, owners.titles],
    ['description', description, owners.descriptions]
  ]) {
    if (!value) continue
    const existing = entries.get(value)
    if (existing) fail(path, `${kind} duplicates ${existing}`)
    else entries.set(value, path)
  }
}

async function auditTechnicalAssets(baseUrl) {
  const manifestResponse = await fetch(`${baseUrl}/site.webmanifest`)
  if (manifestResponse.status !== 200) {
    fail('/site.webmanifest', `expected HTTP 200, received ${manifestResponse.status}`)
    return
  }
  let manifest
  try { manifest = await manifestResponse.json() } catch { fail('/site.webmanifest', 'invalid JSON'); return }
  for (const [key, expected] of Object.entries({
    name: 'Open City Planner',
    short_name: 'Stadtplaner',
    start_url: '/',
    display: 'standalone',
    background_color: '#f8fafc',
    theme_color: '#154d73'
  })) {
    if (manifest[key] !== expected) fail('/site.webmanifest', `${key} is ${manifest[key]}, expected ${expected}`)
  }
  const expectedIcons = new Map([
    ['/web-app-manifest-192x192.png', 192],
    ['/web-app-manifest-512x512.png', 512]
  ])
  if (!Array.isArray(manifest.icons) || manifest.icons.length !== expectedIcons.size) {
    fail('/site.webmanifest', 'expected exactly two manifest icons')
  }
  for (const icon of manifest.icons || []) {
    const size = expectedIcons.get(icon.src)
    if (!size || icon.sizes !== `${size}x${size}` || icon.type !== 'image/png') {
      fail('/site.webmanifest', `invalid icon declaration ${JSON.stringify(icon)}`)
    }
  }

  for (const [path, size] of [
    ['/favicon-96x96.png', 96],
    ['/apple-touch-icon.png', 180],
    ...expectedIcons,
    ['/branding/stadtplaner-social-card.png', [1200, 630]]
  ]) {
    const response = await fetch(`${baseUrl}${path}`)
    if (response.status !== 200) { fail(path, `expected HTTP 200, received ${response.status}`); continue }
    const dimensions = pngDimensions(await response.arrayBuffer())
    const expected = Array.isArray(size) ? size : [size, size]
    if (dimensions[0] !== expected[0] || dimensions[1] !== expected[1]) {
      fail(path, `is ${dimensions.join('x')}, expected ${expected.join('x')}`)
    }
  }
  for (const path of ['/favicon.ico', '/branding/ok-lab-flensburg.svg']) {
    const response = await fetch(`${baseUrl}${path}`)
    if (response.status !== 200) fail(path, `expected HTTP 200, received ${response.status}`)
  }
}

function auditDynamicSocialImage(path, html, expectedPath) {
  const page = parseHtmlSeo(html)
  const values = [
    page.meta.find(item => item.property === 'og:image')?.content,
    page.meta.find(item => item.name === 'twitter:image')?.content
  ]
  for (const value of values) {
    if (!value) continue
    const url = new URL(value)
    if (url.origin !== SEO_AUDIT_PUBLIC_API_ORIGIN) fail(path, `social image uses unexpected origin ${url.origin}`)
    if (url.pathname !== expectedPath) fail(path, `social image uses unexpected path ${url.pathname}`)
    if (url.searchParams.get('width') !== '1200' || url.searchParams.get('height') !== '630') {
      fail(path, 'social image is not 1200x630')
    }
  }
}

function auditDefaultSocialImage(path, html) {
  const page = parseHtmlSeo(html)
  const expected = `${SEO_AUDIT_SITE_ORIGIN}/branding/stadtplaner-social-card.png`
  for (const value of [
    page.meta.find(item => item.property === 'og:image')?.content,
    page.meta.find(item => item.name === 'twitter:image')?.content
  ]) {
    if (value !== expected) fail(path, `default social image is ${value || 'missing'}, expected ${expected}`)
  }
}

function pngDimensions(buffer) {
  const bytes = new Uint8Array(buffer)
  if (bytes[1] !== 80 || bytes[2] !== 78 || bytes[3] !== 71) return [0, 0]
  const view = new DataView(buffer)
  return [view.getUint32(16), view.getUint32(20)]
}

function startFrontend(port, internalApiBaseUrl) {
  const child = spawn(process.execPath, [outputEntry.pathname], {
    env: {
      ...process.env,
      NODE_ENV: 'production',
      NITRO_HOST: '127.0.0.1',
      NITRO_PORT: String(port),
      NUXT_API_INTERNAL_BASE_URL: internalApiBaseUrl,
      NUXT_PUBLIC_API_BASE_URL: `${SEO_AUDIT_PUBLIC_API_ORIGIN}/api/v1`,
      NUXT_PUBLIC_SITE_URL: SEO_AUDIT_SITE_ORIGIN
    },
    stdio: ['ignore', 'pipe', 'pipe']
  })
  let logs = ''
  const capture = chunk => { logs = `${logs}${chunk}`.slice(-4000) }
  child.stdout.on('data', capture)
  child.stderr.on('data', capture)
  child.auditLogs = () => logs
  return child
}

async function waitForServer(baseUrl, child) {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`production server exited with ${child.exitCode}: ${child.auditLogs()}`)
    try {
      const response = await fetch(`${baseUrl}/robots.txt`)
      if (response.ok) return
    } catch { /* server is still starting */ }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error(`production server did not become ready: ${child.auditLogs()}`)
}

async function availablePort() {
  const server = createServer()
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('Could not reserve SEO audit port')
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  return address.port
}

function report(path, messages) {
  for (const message of messages) fail(path, message)
}

function fail(path, message) {
  failures.push(`${path}: ${message}`)
}
