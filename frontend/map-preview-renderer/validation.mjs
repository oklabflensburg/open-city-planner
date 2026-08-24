const ALLOWED_SIZES = new Set(['320x180', '640x360', '800x450', '1200x630'])
const ALLOWED_PAYLOAD_KEYS = new Set(['geometry', 'bbox', 'width', 'height', 'featureKind', 'category'])

function validPosition(value) {
  return Array.isArray(value) && value.length === 2
    && Number.isFinite(value[0]) && value[0] >= -180 && value[0] <= 180
    && Number.isFinite(value[1]) && value[1] >= -90 && value[1] <= 90
}

function validNestedCoordinates(value, depth, counter) {
  if (depth === 0) {
    counter.count += 1
    return counter.count <= 50_000 && validPosition(value)
  }
  return Array.isArray(value) && value.length > 0
    && value.every(item => validNestedCoordinates(item, depth - 1, counter))
}

export function validPayload(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  if (!Object.keys(value).every(key => ALLOWED_PAYLOAD_KEYS.has(key))) return false
  const geometry = value.geometry
  if (!geometry || typeof geometry !== 'object' || Array.isArray(geometry)) return false
  if (!Object.keys(geometry).every(key => ['type', 'coordinates'].includes(key))) return false
  const coordinateDepth = geometry.type === 'Polygon' ? 2 : geometry.type === 'MultiPolygon' ? 3 : -1
  if (coordinateDepth < 0 || !validNestedCoordinates(geometry.coordinates, coordinateDepth, { count: 0 })) return false
  if (!Array.isArray(value.bbox) || value.bbox.length !== 4 || !value.bbox.every(Number.isFinite)) return false
  const [west, south, east, north] = value.bbox
  if (west < -180 || east > 180 || south < -90 || north > 90 || west >= east || south >= north) return false
  if (!ALLOWED_SIZES.has(`${value.width}x${value.height}`)) return false
  if (!['polygon', 'area'].includes(value.featureKind)) return false
  return value.category == null || (typeof value.category === 'string' && value.category.length <= 64)
}
