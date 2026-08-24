import type { AnalysisArea, AnalysisAreaType } from '~/types/analysisArea'

export function countAnalysisAreasByType(
  areas: AnalysisArea[],
  areaType: AnalysisAreaType
) {
  return areas.filter(area => area.area_type === areaType).length
}

export function sortAnalysisAreasByName(areas: AnalysisArea[]) {
  return [...areas].sort((left, right) => left.name.localeCompare(right.name, 'de'))
}
