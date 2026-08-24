import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createNativeRenderer } from './rendering.mjs'

const directory = path.dirname(fileURLToPath(import.meta.url))
const host = process.env.MAP_PREVIEW_HOST || '127.0.0.1'
const port = Number(process.env.MAP_PREVIEW_PORT || 3020)
const stylePath = process.env.MAP_PREVIEW_STYLE_PATH || path.join(directory, '..', 'public', 'map-styles', 'stadtplaner-light.json')
const maxConcurrent = Number(process.env.MAP_PREVIEW_MAX_CONCURRENT || 2)
let activeRenders = 0

function json(response, status, body) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  response.end(JSON.stringify(body))
}

function validPayload(value) {
  return value && typeof value === 'object'
    && ['Polygon', 'MultiPolygon'].includes(value.geometry?.type)
    && Array.isArray(value.bbox) && value.bbox.length === 4 && value.bbox.every(Number.isFinite)
    && [[320, 180], [640, 360], [800, 450], [1200, 630]].some(([width, height]) => value.width === width && value.height === height)
    && ['polygon', 'area'].includes(value.featureKind)
    && (value.category == null || typeof value.category === 'string')
}

const render = await createNativeRenderer(stylePath)
createServer((request, response) => {
  if (request.method === 'GET' && request.url === '/health') return json(response, 200, { status: 'ok', renderer: 'maplibre-native' })
  if (request.method !== 'POST' || request.url !== '/render') return json(response, 404, { error: 'Not found' })
  if (activeRenders >= maxConcurrent) return json(response, 503, { error: 'Renderer busy' })
  const chunks = []
  let length = 0
  request.on('data', (chunk) => {
    length += chunk.length
    if (length > 2 * 1024 * 1024) request.destroy()
    else chunks.push(chunk)
  })
  request.on('end', async () => {
    let payload
    try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch { return json(response, 400, { error: 'Invalid JSON' }) }
    if (!validPayload(payload)) return json(response, 422, { error: 'Invalid render payload' })
    activeRenders += 1
    try {
      const image = await render(payload)
      response.writeHead(200, { 'Content-Type': 'image/webp', 'Content-Length': image.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
      response.end(image)
    } catch (error) {
      console.error(JSON.stringify({ level: 'error', message: 'Map render failed', error: String(error) }))
      if (!response.headersSent) json(response, 502, { error: 'Map render failed' })
      else response.destroy()
    } finally { activeRenders -= 1 }
  })
}).listen(port, host, () => {
  console.log(JSON.stringify({ level: 'info', message: 'Map preview renderer ready', host, port, stylePath }))
})
