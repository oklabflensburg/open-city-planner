export type OsmObjectType = 'node' | 'way' | 'relation'

export function getOsmObjectUrl(type?: string, id?: string | number) {
  if (!type || !['node', 'way', 'relation'].includes(type) || id == null) return null
  const normalizedId = String(id)
  if (!/^\d+$/.test(normalizedId)) return null
  return `https://www.openstreetmap.org/${type}/${normalizedId}`
}

export function getOsmIdEditorUrl(options: { latitude?: number, longitude?: number, zoom?: number } = {}) {
  const { latitude, longitude } = options
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return 'https://www.openstreetmap.org/edit?editor=id'
  }
  const zoom = Math.min(20, Math.max(15, Math.round(options.zoom ?? 19)))
  return `https://www.openstreetmap.org/edit?editor=id#map=${zoom}/${Number(latitude).toFixed(6)}/${Number(longitude).toFixed(6)}`
}

export function getStreetCompleteUrl() {
  return 'https://streetcomplete.app/'
}
