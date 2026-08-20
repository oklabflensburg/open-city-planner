export type MapViewportPadding = { top: number, right: number, bottom: number, left: number }

type MapViewportLayout = {
  viewportWidth: number
  assistantOpen: boolean
  mobilePanelOpen: boolean
  analysisPanelVisible: boolean
}

export function getMapViewportPadding(layout: MapViewportLayout): MapViewportPadding {
  if (layout.viewportWidth < 1280) {
    return {
      top: 104,
      right: 36,
      bottom: layout.mobilePanelOpen ? 300 : 120,
      left: 36
    }
  }

  return {
    top: 48,
    right: layout.analysisPanelVisible ? 48 : 36,
    bottom: 48,
    left: layout.assistantOpen ? 56 : 48
  }
}
