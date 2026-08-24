import { analysisAreaFixture } from './analysisAreas'

export default defineEventHandler((event) => {
  return getCookie(event, 'analysis-area-fixture') === 'empty'
    ? []
    : analysisAreaFixture
})
