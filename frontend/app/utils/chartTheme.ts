import {
  ArcElement, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip,
  type ChartOptions,
} from 'chart.js'

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend)
ChartJS.defaults.font.family = 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
if (import.meta.client && window.matchMedia('(prefers-reduced-motion: reduce)').matches) ChartJS.defaults.animation = false

export const chartPalette = {
  primary: '#086b78', secondary: '#31b8b2', blue: '#2f87b7', green: '#4f9b62',
  accent: '#d8cf28', danger: '#c84655', muted: '#a9bec4', grid: '#d8e5e9', text: '#607781',
}

export const chartSeries = [
  chartPalette.primary, chartPalette.secondary, chartPalette.blue, chartPalette.green,
  chartPalette.accent, '#72c9c4', '#75aeca', '#8ab591', '#dcae45', chartPalette.muted,
]

export function barChartOptions(horizontal = false): ChartOptions<'bar'> {
  return {
    responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? 'y' : 'x', animation: { duration: 220 },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#fff', titleColor: '#18343c', bodyColor: '#18343c', borderColor: '#d8e5e9', borderWidth: 1, padding: 10, cornerRadius: 8, displayColors: false },
    },
    scales: {
      x: { beginAtZero: true, grid: { color: chartPalette.grid }, ticks: { color: chartPalette.text, precision: 0 } },
      y: { beginAtZero: true, grid: { display: !horizontal, color: chartPalette.grid }, ticks: { color: chartPalette.text, precision: 0 } },
    },
  }
}

export function doughnutChartOptions(): ChartOptions<'doughnut'> {
  return {
    responsive: true, maintainAspectRatio: false, cutout: '62%', animation: { duration: 220 },
    plugins: {
      legend: { position: 'bottom', labels: { color: chartPalette.text, boxWidth: 10, boxHeight: 10, padding: 12, usePointStyle: true } },
      tooltip: { backgroundColor: '#fff', titleColor: '#18343c', bodyColor: '#18343c', borderColor: '#d8e5e9', borderWidth: 1, padding: 10, cornerRadius: 8 },
    },
  }
}
