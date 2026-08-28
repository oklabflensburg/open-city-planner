import type { AnalysisArea, AnalysisAreaAnalytics, AnalysisAreaComparison, AnalysisAreaDetail, AnalysisAreaPolygon, AreaStatisticSeries, AreaStatistics } from '../types/analysisArea'
import { useModuleHttp } from '#frontend-module-sdk'

export function useAnalysisAreaApi() {
  const { request } = useModuleHttp()

  return {
    list: () => request<AnalysisArea[]>('/analysis-areas'),
    bySlug: (slug: string) => request<AnalysisAreaDetail>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}`),
    analyticsBySlug: (slug: string) => request<AnalysisAreaAnalytics>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/analytics`),
    comparisonBySlug: (slug: string) => request<AnalysisAreaComparison>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/comparison`),
    polygonsBySlug: (slug: string, limit = 8) => request<AnalysisAreaPolygon[]>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/polygons?limit=${limit}`),
    statisticsBySlug: (slug: string) => request<AreaStatistics>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/statistics`),
    statisticSeriesBySlug: (slug: string, metric: string) => request<AreaStatisticSeries>(`/analysis-areas/by-slug/${encodeURIComponent(slug)}/statistics/${encodeURIComponent(metric)}`)
  }
}
