import { createServer } from 'node:http'
import { realpathSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createNativeRenderer } from './rendering.mjs'
import { validPayload } from './validation.mjs'

const directory = path.dirname(fileURLToPath(import.meta.url))
const host = process.env.MAP_PREVIEW_HOST || '127.0.0.1'
const port = Number(process.env.MAP_PREVIEW_PORT || 3020)
const stylePath = process.env.MAP_PREVIEW_STYLE_PATH || path.join(directory, '..', 'public', 'map-styles', 'stadtplaner-light.json')
const maxConcurrent = Number(process.env.MAP_PREVIEW_MAX_CONCURRENT || 2)
const releaseRoot = process.env.STADTPLANER_RELEASE_ROOT || ''
const releaseSha = releaseRoot ? path.basename(realpathSync(releaseRoot)) : process.env.STADTPLANER_RELEASE_SHA || 'dev'
const expectedStyleHash = process.env.MAP_PREVIEW_STYLE_HASH || ''
let activeRenders = 0

if (!['127.0.0.1', '::1'].includes(host)) throw new Error('Map preview renderer must bind to loopback')
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('MAP_PREVIEW_PORT is invalid')
if (!Number.isInteger(maxConcurrent) || maxConcurrent < 1 || maxConcurrent > 8) throw new Error('MAP_PREVIEW_MAX_CONCURRENT must be between 1 and 8')

function json(response, status, body) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  response.end(JSON.stringify(body))
}

const renderer = await createNativeRenderer(stylePath)
if (expectedStyleHash && renderer.styleHash !== expectedStyleHash) throw new Error('MAP_PREVIEW_STYLE_HASH does not match the release style')

const healthMetadata = {
  renderer: 'maplibre-native',
  rendererVersion: renderer.rendererVersion,
  releaseSha,
  styleHash: renderer.styleHash
}
const smokePayload = {
  geometry: { type: 'Polygon', coordinates: [[[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]] },
  bbox: [9.429, 54.779, 9.432, 54.782],
  width: 320,
  height: 180,
  featureKind: 'area',
  category: null
}
let smokeImage = null
let readinessError = null
const readiness = renderer.render(smokePayload)
  .then((image) => { smokeImage = image })
  .catch((error) => {
    readinessError = error
    console.error(JSON.stringify({ level: 'error', message: 'Map renderer readiness smoke failed', error: String(error), releaseSha }))
  })

createServer((request, response) => {
  if (request.method === 'GET' && request.url === '/health/live') return json(response, 200, { status: 'ok', ...healthMetadata })
  if (request.method === 'GET' && request.url === '/health/info') return json(response, 200, { status: readinessError ? 'error' : smokeImage ? 'ready' : 'starting', ...healthMetadata })
  if (request.method === 'GET' && request.url === '/health/ready') return json(response, smokeImage ? 200 : 503, { status: smokeImage ? 'ok' : readinessError ? 'error' : 'starting', ...healthMetadata })
  if (request.method === 'GET' && request.url === '/health/smoke.webp') {
    if (!smokeImage) return json(response, 503, { error: readinessError ? 'Renderer smoke failed' : 'Renderer starting' })
    response.writeHead(200, { 'Content-Type': 'image/webp', 'Content-Length': smokeImage.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
    return response.end(smokeImage)
  }
  if (request.method !== 'POST' || request.url !== '/render') return json(response, 404, { error: 'Not found' })
  if (activeRenders >= maxConcurrent) return json(response, 503, { error: 'Renderer busy' })
  const chunks = []
  let length = 0
  let tooLarge = false
  request.on('data', (chunk) => {
    length += chunk.length
    if (length > 2 * 1024 * 1024) {
      tooLarge = true
      chunks.length = 0
    }
    else chunks.push(chunk)
  })
  request.on('end', async () => {
    if (tooLarge) return json(response, 413, { error: 'Render payload too large' })
    let payload
    try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch { return json(response, 400, { error: 'Invalid JSON' }) }
    if (!validPayload(payload)) return json(response, 422, { error: 'Invalid render payload' })
    activeRenders += 1
    try {
      await readiness
      if (!smokeImage) return json(response, 503, { error: 'Renderer not ready' })
      const image = await renderer.render(payload)
      response.writeHead(200, { 'Content-Type': 'image/webp', 'Content-Length': image.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
      response.end(image)
    } catch (error) {
      console.error(JSON.stringify({ level: 'error', message: 'Map render failed', error: String(error) }))
      if (!response.headersSent) json(response, 502, { error: 'Map render failed' })
      else response.destroy()
    } finally { activeRenders -= 1 }
  })
}).listen(port, host, () => {
  console.log(JSON.stringify({ level: 'info', message: 'Map preview renderer listening', host, port, stylePath, ...healthMetadata }))
})
