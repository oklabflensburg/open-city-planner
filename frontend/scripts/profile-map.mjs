import { writeFile } from 'node:fs/promises'

const port = Number(process.env.CHROME_DEBUG_PORT || 9223)
const profileUrl = process.env.PROFILE_URL || 'http://127.0.0.1:3000/'
const mobileProfile = process.env.PROFILE_MOBILE === 'true'
const target = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(profileUrl)}`, { method: 'PUT' }).then(response => response.json())
const socket = new WebSocket(target.webSocketDebuggerUrl)
let sequence = 0
const pending = new Map()
const browserErrors = []

socket.addEventListener('message', async (event) => {
  const raw = typeof event.data === 'string' ? event.data : await event.data.text()
  const message = JSON.parse(raw)
  if (message.method === 'Log.entryAdded' && ['error', 'warning'].includes(message.params.entry.level)) {
    browserErrors.push(`${message.params.entry.level}: ${message.params.entry.text}`)
  }
  if (message.method === 'Runtime.exceptionThrown') {
    browserErrors.push(`exception: ${message.params.exceptionDetails.text}`)
  }
  if (!message.id) return
  const handler = pending.get(message.id)
  if (!handler) return
  pending.delete(message.id)
  if (message.error) handler.reject(new Error(message.error.message))
  else handler.resolve(message.result)
})
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})

function command(method, params = {}) {
  const id = ++sequence
  const response = new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
  socket.send(JSON.stringify({ id, method, params }))
  return response
}

async function evaluate(expression, awaitPromise = true) {
  const result = await command('Runtime.evaluate', { expression, awaitPromise, returnByValue: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
  return result.result.value
}

const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
async function performanceMetrics() {
  const result = await command('Performance.getMetrics')
  return Object.fromEntries(result.metrics.map(metric => [metric.name, metric.value]))
}
await command('Runtime.enable')
await command('Page.enable')
await command('Log.enable')
await command('Performance.enable')
await command('Network.enable')
if (mobileProfile) {
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await command('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 1 })
}
await command('Page.addScriptToEvaluateOnNewDocument', {
  source: `
    window.__profile = { requests: [], longTasks: [], frames: [] };
    const originalFetch = window.fetch;
    window.fetch = (...args) => {
      const url = String(args[0] instanceof Request ? args[0].url : args[0]);
      window.__profile.requests.push({ url, at: performance.now() });
      return originalFetch(...args);
    };
    new PerformanceObserver(list => {
      for (const entry of list.getEntries()) window.__profile.longTasks.push({ start: entry.startTime, duration: entry.duration });
    }).observe({ type: 'longtask', buffered: true });
    let previous = performance.now();
    const frame = now => { window.__profile.frames.push(now - previous); previous = now; requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
  `
})
await command('Page.navigate', { url: profileUrl })

let mapReady = false
for (let attempt = 0; attempt < 120; attempt++) {
  const ready = await evaluate(`Boolean(window.__stadtplanerMapPerformance?.map)`).catch(() => false)
  if (ready) {
    mapReady = true
    break
  }
  await wait(250)
}
if (!mapReady) {
  const pageState = await evaluate(`({ url: location.href, text: document.body.innerText.slice(0, 1000) })`)
  throw new Error(`Map did not become ready: ${JSON.stringify(pageState)}`)
}
process.stderr.write('map ready\n')

async function waitForIdle() {
  await evaluate(`new Promise(resolve => {
    const map = window.__stadtplanerMapPerformance.map;
    if (map.loaded()) resolve(true); else map.once('idle', () => resolve(true));
    setTimeout(() => resolve(true), 3000);
  })`)
  await wait(350)
  for (let attempt = 0; attempt < 24; attempt++) {
    if (await evaluate(`window.__stadtplanerMapPerformance.snapshot().viewportCovered === 1`)) return
    await wait(250)
  }
}

async function dragFor(durationMs = 3000) {
  const featureStats = await evaluate(`(() => {
    const map = window.__stadtplanerMapPerformance.map;
    const layers = map.getStyle().layers.map(layer => layer.id);
    const custom = layers.filter(id => id.startsWith('osm-') || id.startsWith('overview-'));
    return {
      osmSourceFeatures: map.querySourceFeatures('osm-pois').length + map.querySourceFeatures('osm-polygons').length,
      renderedCustomFeatures: map.queryRenderedFeatures({ layers: custom }).length
    };
  })()`)
  await evaluate(`window.__profile.frames = []; window.__profile.longTasks = []; window.__profile.requests = []; window.__stadtplanerMapPerformance.reset()`)
  const metricsBefore = await performanceMetrics()
  const box = await evaluate(`(() => { const r = document.querySelector('.maplibregl-canvas').getBoundingClientRect(); return { x:r.x, y:r.y, width:r.width, height:r.height } })()`)
  const startX = box.x + box.width * 0.62
  const startY = box.y + box.height * 0.52
  if (mobileProfile) await command('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: startX, y: startY, id: 1 }] })
  else await command('Input.dispatchMouseEvent', { type: 'mousePressed', x: startX, y: startY, button: 'left', clickCount: 1 })
  const steps = 60
  for (let index = 0; index < steps; index++) {
    const x = startX + Math.sin(index / 12) * box.width * 0.12
    const y = startY + Math.sin(index / 17) * box.height * 0.08
    if (mobileProfile) await command('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y, id: 1 }] })
    else await command('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'left', buttons: 1 })
    await wait(durationMs / steps)
  }
  const beforeRelease = await evaluate(`({
    snapshot: window.__stadtplanerMapPerformance.snapshot(),
    requests: window.__profile.requests.filter(item => item.url.includes('/osm/features')).length,
    frames: window.__profile.frames.slice(),
    longTasks: window.__profile.longTasks.slice()
  })`)
  const metricsAfter = await performanceMetrics()
  if (mobileProfile) await command('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  else await command('Input.dispatchMouseEvent', { type: 'mouseReleased', x: startX, y: startY, button: 'left', clickCount: 1 })
  await wait(700)
  const afterReleaseRequests = await evaluate(`window.__profile.requests.filter(item => item.url.includes('/osm/features')).length`)
  const frames = beforeRelease.frames.filter(value => value < 1000)
  const slowFrames = frames.filter(value => value > 20).length
  return {
    ...featureStats,
    ...beforeRelease.snapshot,
    activeDragRequests: beforeRelease.requests,
    requestsAfterMoveend: afterReleaseRequests,
    frameCount: frames.length,
    fps: Number((1000 / (frames.reduce((sum, value) => sum + value, 0) / frames.length)).toFixed(1)),
    slowFramePercent: Number((slowFrames * 100 / frames.length).toFixed(1)),
    maxFrameMs: Number(Math.max(...frames).toFixed(1)),
    longTasks: beforeRelease.longTasks.length,
    longTaskMs: Number(beforeRelease.longTasks.reduce((sum, task) => sum + task.duration, 0).toFixed(1)),
    taskMs: Number(((metricsAfter.TaskDuration - metricsBefore.TaskDuration) * 1000).toFixed(1)),
    scriptingMs: Number(((metricsAfter.ScriptDuration - metricsBefore.ScriptDuration) * 1000).toFixed(1)),
    layoutMs: Number(((metricsAfter.LayoutDuration - metricsBefore.LayoutDuration) * 1000).toFixed(1)),
    recalcStyleMs: Number(((metricsAfter.RecalcStyleDuration - metricsBefore.RecalcStyleDuration) * 1000).toFixed(1))
  }
}

const results = []
const zooms = process.env.PROFILE_ZOOMS?.split(',').map(Number) || [13, 15, 17, 19]
const hiddenLayerGroup = process.env.PROFILE_HIDE || ''
for (const zoom of zooms) {
  process.stderr.write(`profiling z${zoom}\n`)
  await evaluate(`window.__stadtplanerMapPerformance.map.jumpTo({ center: [9.435, 54.783], zoom: ${zoom} }); true`)
  await waitForIdle()
  if (hiddenLayerGroup) {
    await evaluate(`(() => {
      const map = window.__stadtplanerMapPerformance.map;
      for (const layer of map.getStyle().layers) {
        const custom = layer.id.startsWith('osm-') || layer.id.startsWith('overview-');
        const group = ${JSON.stringify(hiddenLayerGroup)};
        const hide = group === 'custom' ? custom
          : group === 'osm' ? layer.id.startsWith('osm-')
            : group === 'overview' && layer.id.startsWith('overview-');
        if (hide) map.setLayoutProperty(layer.id, 'visibility', 'none');
      }
      return true;
    })()`)
    await wait(500)
  }
  results.push({ zoom, ...(await dragFor()) })
  process.stderr.write(`finished z${zoom}\n`)
}

let routeCycleResult = null
const routeCycles = Number(process.env.PROFILE_ROUTE_CYCLES || 0)
if (routeCycles) {
  await command('HeapProfiler.enable')
  await command('HeapProfiler.collectGarbage')
  const before = await command('Memory.getDOMCounters')
  for (let cycle = 0; cycle < routeCycles; cycle++) {
    await evaluate(`document.querySelector('a[href="/ueber-das-projekt"]')?.click(); true`)
    await wait(500)
    await evaluate(`document.querySelector('a[href="/"]')?.click(); true`)
    for (let attempt = 0; attempt < 40; attempt++) {
      if (await evaluate(`Boolean(window.__stadtplanerMapPerformance?.map)`).catch(() => false)) break
      await wait(100)
    }
    await wait(500)
  }
  await command('HeapProfiler.collectGarbage')
  const after = await command('Memory.getDOMCounters')
  routeCycleResult = {
    routeCycles,
    before,
    after,
    canvases: await evaluate(`document.querySelectorAll('.maplibregl-canvas').length`),
    maps: await evaluate(`Number(Boolean(window.__stadtplanerMapPerformance?.map))`)
  }
}

if (process.env.PROFILE_SCREENSHOT) {
  const screenshot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(process.env.PROFILE_SCREENSHOT, Buffer.from(screenshot.data, 'base64'))
}
process.stdout.write(`${JSON.stringify({ results, routeCycleResult, browserErrors }, null, 2)}\n`)
await command('Page.close')
socket.close()
