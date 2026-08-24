import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import path from 'node:path'
import sharp from 'sharp'
import industries from '../app/config/industries.json' with { type: 'json' }

const require = createRequire(import.meta.url)
const TILE_SIZE = 512
const FALLBACK_COLOR = '#789098'
const AREA_COLOR = '#086b78'
const VERSATILES_SOURCE = 'versatiles-shortbread'

export function cameraForBounds(bbox, width, height) {
  const [west, south, east, north] = bbox.map(Number)
  const padding = Math.max(24, Math.min(72, Math.round(Math.min(width, height) * 0.12)))
  const mercatorX = longitude => (longitude + 180) / 360
  const mercatorY = (latitude) => {
    const bounded = Math.max(-85.05112878, Math.min(85.05112878, latitude))
    const radians = bounded * Math.PI / 180
    return (1 - Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI) / 2
  }
  const inverseY = y => Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI
  const x1 = mercatorX(west)
  const x2 = mercatorX(east)
  const y1 = mercatorY(north)
  const y2 = mercatorY(south)
  const zoomX = Math.log2(Math.max(1, width - 2 * padding) / (TILE_SIZE * Math.max(x2 - x1, 1e-9)))
  const zoomY = Math.log2(Math.max(1, height - 2 * padding) / (TILE_SIZE * Math.max(y2 - y1, 1e-9)))
  return {
    center: [(west + east) / 2, inverseY((y1 + y2) / 2)],
    zoom: Math.max(0, Math.min(18, zoomX, zoomY))
  }
}

export function styleWithHighlight(style, { geometry, category, featureKind }) {
  const result = structuredClone(style)
  const color = featureKind === 'area'
    ? AREA_COLOR
    : industries.find(item => item.key === category)?.color || FALLBACK_COLOR
  result.sources['stadtplaner-preview-highlight'] = {
    type: 'geojson', data: { type: 'Feature', properties: {}, geometry }
  }
  result.layers.push(
    { id: 'stadtplaner-preview-highlight-fill', type: 'fill', source: 'stadtplaner-preview-highlight', paint: { 'fill-color': color, 'fill-opacity': featureKind === 'area' ? 0.2 : 0.42 } },
    { id: 'stadtplaner-preview-highlight-line', type: 'line', source: 'stadtplaner-preview-highlight', paint: { 'line-color': color, 'line-width': 3 } }
  )
  return result
}

export function attributionFromStyle(style) {
  const values = Object.values(style.sources || {})
    .map(source => source?.attribution)
    .filter(Boolean)
    .map(value => String(value).replace(/[<>]/g, '').replace(/\s+/g, ' ').trim())
  return [...new Set(values)].join(' · ') || '© OpenStreetMap contributors'
}

function escapeXml(value) {
  return value.replace(/[<>&"']/g, character => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[character])
}

function attributionOverlay(style, width, height) {
  const text = escapeXml(attributionFromStyle(style))
  return Buffer.from(`<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="${height - 25}" width="${width}" height="25" fill="#fff" fill-opacity="0.9"/><text x="${width - 8}" y="${height - 8}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#263238">${text}</text></svg>`)
}

export function allowedResource(url) {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' && parsed.hostname === 'tiles.versatiles.org'
      && (parsed.pathname.startsWith('/tiles/osm/') || parsed.pathname.startsWith('/assets/glyphs/'))
      && !parsed.username && !parsed.password
  } catch { return false }
}

export function validateStyle(style) {
  if (!style || style.version !== 8 || !Array.isArray(style.layers)) throw new Error('Map preview style must use Style Specification version 8')
  const source = style.sources?.[VERSATILES_SOURCE]
  if (source?.type !== 'vector' || !Array.isArray(source.tiles) || source.tiles.length === 0) throw new Error(`Map preview style must define vector source ${VERSATILES_SOURCE}`)
  if (!source.tiles.every(allowedResource)) throw new Error('Map preview style contains a disallowed tile URL')
  if (typeof style.glyphs !== 'string' || !allowedResource(style.glyphs)) throw new Error('Map preview style must define the approved VersaTiles glyph URL')
  if (!source.attribution) throw new Error('Map preview style source must define attribution')
  return style
}

function requestResource(request, callback) {
  if (!allowedResource(request.url)) return callback(new Error(`Blocked map resource: ${request.url}`))
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10_000)
  fetch(request.url, { signal: controller.signal, redirect: 'error' })
    .then(async (response) => {
      if (!response.ok) throw new Error(`Map resource returned HTTP ${response.status}`)
      callback(null, {
        data: Buffer.from(await response.arrayBuffer()),
        etag: response.headers.get('etag') || undefined,
        modified: response.headers.get('last-modified') ? new Date(response.headers.get('last-modified')) : undefined,
        expires: response.headers.get('expires') ? new Date(response.headers.get('expires')) : undefined
      })
    })
    .catch(error => callback(error))
    .finally(() => clearTimeout(timer))
}

export async function createNativeRenderer(stylePath) {
  const styleBytes = await readFile(path.resolve(stylePath))
  const baseStyle = validateStyle(JSON.parse(styleBytes.toString('utf8')))
  const mbgl = require('@maplibre/maplibre-gl-native')
  const nativePackage = require('@maplibre/maplibre-gl-native/package.json')
  const render = async function render(payload) {
    const map = new mbgl.Map({ request: requestResource, ratio: 1 })
    try {
      map.load(styleWithHighlight(baseStyle, payload))
      const raw = await new Promise((resolve, reject) => {
        map.render({ ...cameraForBounds(payload.bbox, payload.width, payload.height), width: payload.width, height: payload.height }, (error, buffer) => error ? reject(error) : resolve(buffer))
      })
      return await sharp(raw, { raw: { width: payload.width, height: payload.height, channels: 4 } })
        .composite([{ input: attributionOverlay(baseStyle, payload.width, payload.height) }])
        .webp({ quality: 84, effort: 4 })
        .toBuffer()
    } finally { map.release() }
  }
  return {
    render,
    rendererVersion: nativePackage.version,
    styleHash: createHash('sha256').update(styleBytes).digest('hex')
  }
}
