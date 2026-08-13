export function formatMetricPercent(value: number | null | undefined) {
  return value == null ? '—' : `${value.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} %`
}

export function formatMetricIndex(value: number | null | undefined) {
  return value == null ? '—' : value.toLocaleString('de-DE', { maximumFractionDigits: 2 })
}
