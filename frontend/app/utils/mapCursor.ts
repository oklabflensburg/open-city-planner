import type { Map } from 'maplibre-gl'

export type MapCursorState = 'pan' | 'dragging' | 'interactive' | 'drawing' | 'editing'

const cursorByState: Record<MapCursorState, string> = {
  pan: 'grab',
  dragging: 'grabbing',
  interactive: 'pointer',
  drawing: 'crosshair',
  editing: 'move'
}

export function mapCursorValue(state: MapCursorState) {
  return cursorByState[state]
}

export function setMapCursor(instance: Pick<Map, 'getCanvas'>, state: MapCursorState) {
  instance.getCanvas().style.cursor = mapCursorValue(state)
}
