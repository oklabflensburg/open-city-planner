import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export function mapHostSource() {
  return [
    'app/components/map/MapCanvas.vue',
    'app/composables/useMapCanvasHost.ts',
    'app/map-runtime/MapLifecycle.ts',
    'app/map-runtime/LayerRegistry.ts'
  ].map(path => readFileSync(resolve(import.meta.dirname, '..', path), 'utf8')).join('\n')
}
