import { nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { usePolygonAutosave } from '../app/composables/usePolygonAutosave'

afterEach(() => vi.useRealTimers())

describe('polygon autosave', () => {
  it('debounces and combines quick text edits', async () => {
    vi.useFakeTimers()
    const save = vi.fn().mockResolvedValue({ updated_at: '2026-08-12T12:01:00Z' })
    const autosave = usePolygonAutosave({
      updatedAt: ref('2026-08-12T12:00:00Z'),
      savePublic: save,
      saveVerwaltung: vi.fn(),
      debounceMs: 700
    })

    autosave.schedulePublic({ name: 'Laden' })
    autosave.schedulePublic({ description: 'Am Holm' })
    await vi.advanceTimersByTimeAsync(699)
    expect(save).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)

    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith({
      name: 'Laden',
      description: 'Am Holm',
      expected_updated_at: '2026-08-12T12:00:00Z'
    })
    expect(autosave.status.value).toBe('saved')
  })

  it('runs saves sequentially and uses the newest server version', async () => {
    vi.useFakeTimers()
    let resolveFirst!: (value: { updated_at: string }) => void
    const first = new Promise<{ updated_at: string }>(resolve => { resolveFirst = resolve })
    const save = vi.fn()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce({ updated_at: 'v3' })
    const autosave = usePolygonAutosave({
      updatedAt: ref('v1'), savePublic: save, saveVerwaltung: vi.fn(), debounceMs: 10
    })

    autosave.schedulePublic({ name: 'A' }, true)
    await vi.runOnlyPendingTimersAsync()
    autosave.schedulePublic({ name: 'B' }, true)
    await vi.runOnlyPendingTimersAsync()
    expect(save).toHaveBeenCalledTimes(1)

    resolveFirst({ updated_at: 'v2' })
    await first
    await nextTick()
    await vi.runAllTimersAsync()

    expect(save).toHaveBeenCalledTimes(2)
    expect(save.mock.calls[1]?.[0]).toEqual({ name: 'B', expected_updated_at: 'v2' })
    expect(autosave.status.value).toBe('saved')
  })

  it('keeps failed changes for retry and exposes conflict state', async () => {
    vi.useFakeTimers()
    const conflict = Object.assign(new Error('conflict'), { statusCode: 409 })
    const save = vi.fn().mockRejectedValueOnce(conflict).mockResolvedValueOnce({ updated_at: 'v2' })
    const autosave = usePolygonAutosave({
      updatedAt: ref('v1'), savePublic: save, saveVerwaltung: vi.fn(), debounceMs: 10
    })

    autosave.schedulePublic({ floor: 'EG' }, true)
    await vi.runAllTimersAsync()
    expect(autosave.status.value).toBe('conflict')

    autosave.retry()
    await vi.runAllTimersAsync()
    expect(save).toHaveBeenCalledTimes(2)
    expect(autosave.status.value).toBe('saved')
  })

  it('does not overwrite a newer pending edit when an older request is retried', async () => {
    vi.useFakeTimers()
    let rejectFirst!: (reason: unknown) => void
    const first = new Promise<{ updated_at: string }>((_resolve, reject) => { rejectFirst = reject })
    const save = vi.fn().mockReturnValueOnce(first).mockResolvedValueOnce({ updated_at: 'v2' })
    const autosave = usePolygonAutosave({
      updatedAt: ref('v1'), savePublic: save, saveVerwaltung: vi.fn(), debounceMs: 10
    })

    autosave.schedulePublic({ name: 'Alter Wert' }, true)
    await vi.runOnlyPendingTimersAsync()
    autosave.schedulePublic({ name: 'Neuer Wert' }, true)
    rejectFirst(new Error('offline'))
    await vi.runAllTimersAsync()
    autosave.retry()
    await vi.runAllTimersAsync()

    expect(save.mock.calls[1]?.[0]).toEqual({ name: 'Neuer Wert', expected_updated_at: 'v1' })
  })
})
