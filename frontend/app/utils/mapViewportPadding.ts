export type MapViewportPadding = { top: number, right: number, bottom: number, left: number }

type MapViewportLayout = {
  viewportWidth: number
  viewportHeight: number
  leftPanelExpanded: boolean
  bottomSheetOpen: boolean
  compactPanelOpen: boolean
  analysisPanelVisible: boolean
}

export function getMapViewportPadding(layout: MapViewportLayout): MapViewportPadding {
  const compactWorkbench = layout.viewportWidth >= 900
    && layout.viewportWidth < 1280
    && layout.viewportHeight >= 560

  if (layout.viewportWidth < 1280 && !compactWorkbench) {
    return {
      top: 56,
      right: 36,
      bottom: layout.bottomSheetOpen ? 300 : layout.viewportWidth < 480 ? 156 : 120,
      left: 36
    }
  }

  if (compactWorkbench) {
    // The grid removes the tool panel from MapLibre's actual container. These
    // insets therefore apply to the remaining, fully visible map viewport.
    return { top: 40, right: layout.compactPanelOpen ? 48 : 40, bottom: 96, left: 40 }
  }

  return {
    top: 48,
    right: layout.analysisPanelVisible ? 48 : 36,
    bottom: 48,
    left: layout.leftPanelExpanded ? 56 : 48
  }
}
