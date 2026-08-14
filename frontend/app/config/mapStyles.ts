import type { StyleSpecification } from 'maplibre-gl'

export const DEFAULT_MAP_STYLE_URL = '/map-styles/stadtplaner-light.json'
export const FALLBACK_MAP_STYLE_URL = 'https://tiles.versatiles.org/assets/styles/neutrino/style.json'

export function resolveMapStyleUrl(configuredUrl?: string | null) {
  return configuredUrl?.trim() || DEFAULT_MAP_STYLE_URL
}

export async function loadMapStyle(configuredUrl?: string | null): Promise<StyleSpecification> {
  const primaryUrl = resolveMapStyleUrl(configuredUrl)
  const candidates = primaryUrl === FALLBACK_MAP_STYLE_URL
    ? [primaryUrl]
    : [primaryUrl, FALLBACK_MAP_STYLE_URL]
  const failures: string[] = []

  for (const url of candidates) {
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const style = await response.json() as Partial<StyleSpecification>
      if (style.version !== 8 || !style.sources || !Array.isArray(style.layers)) {
        throw new Error('ungültiges MapLibre-Style-Dokument')
      }
      return style as StyleSpecification
    } catch (error) {
      failures.push(`${url}: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  throw new Error(`Kein Kartenstil konnte geladen werden. ${failures.join(' · ')}`)
}
