import { getHeader, getRequestURL, setHeader } from 'h3'
import { requestIdFor, routeTemplate } from '../utils/observability'

export default defineEventHandler((event) => {
  const started = performance.now()
  const requestId = requestIdFor(getHeader(event, 'x-request-id'))
  event.context.requestId = requestId
  setHeader(event, 'X-Request-ID', requestId)
  event.node.res.once('finish', () => {
    const config = useRuntimeConfig(event)
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: event.node.res.statusCode >= 500 ? 'error' : 'info',
      service: 'stadtplaner-frontend',
      environment: process.env.APP_ENVIRONMENT || config.environment,
      release_sha: process.env.STADTPLANER_RELEASE_SHA || config.releaseSha,
      event: 'http_request_completed',
      request_id: requestId,
      method: event.method,
      route: routeTemplate(getRequestURL(event).pathname),
      status_code: event.node.res.statusCode,
      duration_ms: Math.round((performance.now() - started) * 1000) / 1000
    }))
  })
})
