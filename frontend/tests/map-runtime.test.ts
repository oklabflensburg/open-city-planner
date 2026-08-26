import type { IControl, Map as MapLibreMap } from 'maplibre-gl'
import { describe, expect, it, vi } from 'vitest'
import type { BoundMapLayerContribution, BoundMapSourceContribution, MapContext } from '#frontend-module-sdk'
import { ControlRegistry } from '../app/map-runtime/ControlRegistry'
import { DrawManager, createTerraDrawAdapter } from '../app/map-runtime/DrawManager'
import { FeatureInfoRegistry } from '../app/map-runtime/FeatureInfoRegistry'
import { InteractionRegistry } from '../app/map-runtime/InteractionRegistry'
import { LayerRegistry } from '../app/map-runtime/LayerRegistry'
import { MapLifecycle } from '../app/map-runtime/MapLifecycle'
import { resolveMapExtensionSnapshot } from '../app/map-runtime/MapRuntime'
import { SelectionManager } from '../app/map-runtime/SelectionManager'
import { DuplicateMapLayerError, DuplicateMapSourceError, UnknownMapSourceError } from '../app/map-runtime/errors'

function source(id: string, moduleId = 'alpha'): BoundMapSourceContribution {
  return {
    id,
    moduleId,
    moduleOrder: 0,
    source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
  }
}

function layer(id: string, sourceId: string, group: BoundMapLayerContribution['group'] = 'overlay', priority = 100): BoundMapLayerContribution {
  return { id, sourceId, moduleId: 'alpha', moduleOrder: 0, group, priority, layer: { type: 'circle' } }
}

function mapMock() {
  const sources = new Map<string, unknown>()
  const layers: string[] = []
  const eventHandlers = new Map<string, Set<(event: unknown) => void>>()
  const canvasHandlers = new Map<string, Set<EventListener>>()
  const canvas = {
    tabIndex: -1,
    hasAttribute: () => false,
    addEventListener: vi.fn((event: string, handler: EventListener) => {
      const handlers = canvasHandlers.get(event) ?? new Set()
      handlers.add(handler)
      canvasHandlers.set(event, handlers)
    }),
    removeEventListener: vi.fn((event: string, handler: EventListener) => canvasHandlers.get(event)?.delete(handler))
  }
  const map = {
    addSource: vi.fn((id: string, definition: unknown) => sources.set(id, definition)),
    getSource: vi.fn((id: string) => sources.get(id)),
    removeSource: vi.fn((id: string) => sources.delete(id)),
    addLayer: vi.fn((definition: { id: string }) => layers.push(definition.id)),
    getLayer: vi.fn((id: string) => layers.includes(id) ? { id } : undefined),
    removeLayer: vi.fn((id: string) => { layers.splice(layers.indexOf(id), 1) }),
    moveLayer: vi.fn((id: string, beforeId?: string) => {
      layers.splice(layers.indexOf(id), 1)
      const index = beforeId ? layers.indexOf(beforeId) : layers.length
      layers.splice(index, 0, id)
    }),
    on: vi.fn((event: string, handler: (event: unknown) => void) => {
      const handlers = eventHandlers.get(event) ?? new Set()
      handlers.add(handler)
      eventHandlers.set(event, handlers)
    }),
    off: vi.fn((event: string, handler: (event: unknown) => void) => eventHandlers.get(event)?.delete(handler)),
    emit: (event: string, value: unknown = {}) => eventHandlers.get(event)?.forEach(handler => handler(value)),
    queryRenderedFeatures: vi.fn(() => [{ id: 'feature' }]),
    getCanvas: () => canvas,
    addControl: vi.fn(),
    removeControl: vi.fn(),
    resize: vi.fn(),
    remove: vi.fn()
  }
  return { map: map as unknown as MapLibreMap, sources, layers, eventHandlers, canvas }
}

describe('MapLifecycle', () => {
  it('creates, reports ready, coalesces resize and destroys the map', async () => {
    const { map } = mapMock()
    const scheduled: Array<() => void> = []
    const observer = { observe: vi.fn(), disconnect: vi.fn() }
    const ready = vi.fn()
    const lifecycle = new MapLifecycle({
      createMap: vi.fn(async () => map),
      createResizeObserver: () => observer,
      scheduleFrame: handler => scheduled.push(handler) - 1,
      cancelFrame: vi.fn()
    })
    lifecycle.onReady(ready)
    await lifecycle.create({} as HTMLElement)
    ;(map as never as { emit(event: string): void }).emit('load')
    await vi.waitFor(() => expect(ready).toHaveBeenCalledWith(map, 'load'))
    lifecycle.resize()
    lifecycle.resize()
    scheduled.at(-1)?.()
    expect(map.resize).toHaveBeenCalledOnce()
    lifecycle.destroy()
    expect(observer.disconnect).toHaveBeenCalledOnce()
    expect(map.remove).toHaveBeenCalledOnce()
  })
})

describe('map extension runtime configuration', () => {
  it('falls back to an empty snapshot when a deployment has no map contribution config', () => {
    expect(resolveMapExtensionSnapshot(undefined)).toEqual({ sources: [], layers: [] })
    expect(resolveMapExtensionSnapshot({})).toEqual({ sources: [], layers: [] })
  })

  it('preserves configured extension definitions', () => {
    const configured = { sources: [source('alpha.data')], layers: [layer('alpha.points', 'alpha.data')] }
    expect(resolveMapExtensionSnapshot(configured)).toEqual(configured)
  })
})

describe('LayerRegistry', () => {
  it('registers sources/layers, rejects duplicates and missing sources', () => {
    const registry = new LayerRegistry()
    registry.registerSource(source('alpha.data'))
    expect(() => registry.registerSource(source('alpha.data'))).toThrowError(DuplicateMapSourceError)
    registry.registerLayer(layer('alpha.points', 'alpha.data'))
    expect(() => registry.registerLayer(layer('alpha.points', 'alpha.data'))).toThrowError(DuplicateMapLayerError)
    expect(() => registry.registerLayer(layer('alpha.missing', 'alpha.unknown'))).toThrowError(UnknownMapSourceError)
  })

  it('attaches after style readiness, orders deterministically and cleans layers before sources', () => {
    const registry = new LayerRegistry()
    registry.registerSource(source('alpha.data'))
    registry.registerLayer(layer('alpha.overlay', 'alpha.data', 'overlay', 10))
    registry.registerLayer(layer('alpha.analysis', 'alpha.data', 'analysis', 200))
    registry.seal()
    const { map, layers } = mapMock()
    registry.attach(map)
    expect(layers).toEqual(['alpha.analysis', 'alpha.overlay'])
    registry.detach()
    expect(map.removeLayer.mock.invocationCallOrder.at(-1)).toBeLessThan(map.removeSource.mock.invocationCallOrder[0]!)
    registry.attach(map)
    expect(layers).toEqual(['alpha.analysis', 'alpha.overlay'])
  })
})

describe('ControlRegistry and InteractionRegistry', () => {
  const context = { features: { queryRendered: () => [{ id: 'feature' }] } } as unknown as MapContext

  it('attaches controls at their position and removes them', () => {
    const registry = new ControlRegistry()
    const control = {} as IControl
    registry.register({ id: 'alpha.zoom', moduleId: 'alpha', position: 'top-right', accessibleLabel: 'Zoom', create: () => control })
    const { map } = mapMock()
    registry.attach(map, context)
    expect(map.addControl).toHaveBeenCalledWith(expect.objectContaining({ onAdd: expect.any(Function) }), 'top-right')
    registry.unregister('alpha.zoom')
    expect(map.removeControl).toHaveBeenCalledWith(expect.objectContaining({ onRemove: expect.any(Function) }))
  })

  it('dispatches one listener by priority, layer scope and handled semantics', async () => {
    const registry = new InteractionRegistry()
    const calls: string[] = []
    registry.register({ id: 'alpha.late', moduleId: 'alpha', event: 'click', priority: 20, handler: () => { calls.push('late') } })
    registry.register({ id: 'alpha.first', moduleId: 'alpha', event: 'click', layerIds: ['alpha.points'], priority: 10, handler: () => { calls.push('first'); return { handled: true } } })
    const { map, eventHandlers } = mapMock()
    ;(map.getLayer as ReturnType<typeof vi.fn>).mockReturnValue({ id: 'alpha.points' })
    registry.attach(map, context)
    expect(eventHandlers.get('click')).toHaveLength(1)
    ;(map as never as { emit(event: string, value: unknown): void }).emit('click', { point: { x: 1, y: 2 } })
    await vi.waitFor(() => expect(calls).toEqual(['first']))
    registry.detach()
    expect(eventHandlers.get('click')).toHaveLength(0)
  })
})

describe('Selection, Draw and FeatureInfo', () => {
  it('selects, replaces, clears and invokes the matching presentation', async () => {
    const manager = new SelectionManager()
    const present = vi.fn()
    manager.registerPresentation({ id: 'alpha.presentation', moduleId: 'alpha', canPresent: () => true, present })
    const first = { moduleId: 'alpha', sourceId: 'alpha.data', layerId: 'alpha.points', featureId: '1' }
    const second = { ...first, featureId: '2' }
    await manager.select(first)
    await manager.select(second)
    expect(manager.current()?.featureId).toBe('2')
    expect(present).toHaveBeenCalledTimes(2)
    manager.clear()
    expect(manager.current()).toBeNull()
  })

  it('owns exactly one draw adapter and cleans it up', () => {
    const adapter = { start: vi.fn(), stop: vi.fn(), setMode: vi.fn(), clear: vi.fn(), destroy: vi.fn() }
    const manager = new DrawManager()
    manager.initialize(() => adapter)
    expect(() => manager.initialize(() => adapter)).toThrow(/already owns/)
    manager.startMode('polygon')
    manager.stop()
    manager.clear()
    manager.destroy()
    expect(adapter.setMode).toHaveBeenCalledWith('polygon')
    expect(adapter.destroy).toHaveBeenCalledOnce()
  })

  it('encapsulates Terra Draw cleanup behind the stable adapter', () => {
    const draw = {
      start: vi.fn(), stop: vi.fn(), setMode: vi.fn(),
      getSnapshot: () => [{ id: 'one' }, { id: 'two' }], removeFeatures: vi.fn()
    }
    const adapter = createTerraDrawAdapter(draw as never)
    adapter.start()
    adapter.setMode('select')
    adapter.destroy()
    expect(draw.removeFeatures).toHaveBeenCalledWith(['one', 'two'])
    expect(draw.stop).toHaveBeenCalledOnce()
  })

  it('uses provider priority and returns undefined without a provider', async () => {
    const registry = new FeatureInfoRegistry()
    const selection = { moduleId: 'alpha', sourceId: 'alpha.data', layerId: 'alpha.points', featureId: '1' }
    expect(await registry.resolve(selection, {} as MapContext)).toBeUndefined()
    registry.register({ id: 'alpha.late', moduleId: 'alpha', priority: 20, canHandle: () => true, resolveFeatureInfo: () => 'late' })
    registry.register({ id: 'alpha.first', moduleId: 'alpha', priority: 10, canHandle: () => true, resolveFeatureInfo: () => 'first' })
    expect(await registry.resolve(selection, {} as MapContext)).toBe('first')
  })
})
