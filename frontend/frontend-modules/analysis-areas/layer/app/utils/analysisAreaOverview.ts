interface AnalysisAreaOverviewItem {
  readonly name: string
  readonly area_type: string
}

export function countAnalysisAreasByType(
  areas: AnalysisAreaOverviewItem[],
  areaType: string
) {
  return areas.filter(area => area.area_type === areaType).length
}

export function sortAnalysisAreasByName<T extends AnalysisAreaOverviewItem>(areas: T[]) {
  return [...areas].sort((left, right) => left.name.localeCompare(right.name, 'de'))
}
