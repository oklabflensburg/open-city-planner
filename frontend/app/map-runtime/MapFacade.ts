import type { Map as MapLibreMap } from 'maplibre-gl'
import type { MapFacade as MapFacadeContract } from '#frontend-module-sdk'

export function createMapFacade(map: MapLibreMap): MapFacadeContract {
  const facade: MapFacadeContract = {
    getCenter: () => {
      const center = map.getCenter()
      return { lng: center.lng, lat: center.lat }
    },
    getZoom: () => map.getZoom(),
    fitBounds: (bounds, options) => { map.fitBounds(bounds, options) },
    flyTo: options => { map.flyTo(options) },
    project: position => {
      const point = map.project(position)
      return { x: point.x, y: point.y }
    },
    unproject: point => {
      const position = map.unproject(point)
      return { lng: position.lng, lat: position.lat }
    }
  }
  return Object.freeze(facade)
}
