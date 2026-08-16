import { describe, expect, it, vi } from 'vitest'
import { createSerialSaveQueue } from '../app/utils/serialSaveQueue'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('serial settings save queue', () => {
  it('merges rapid changes into one patch', async () => {
    const save = vi.fn(async (patch: Record<string, unknown>) => patch)
    const queue = createSerialSaveQueue({ save })

    queue.enqueue({ visibility: 'public' })
    queue.enqueue({ visibility: 'unlisted', enabled: false })
    await queue.flush()

    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith({ visibility: 'unlisted', enabled: false })
  })

  it('runs at most one request and sends changes made during a save afterwards', async () => {
    const first = deferred<Record<string, unknown>>()
    const second = deferred<Record<string, unknown>>()
    const save = vi.fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise)
    const queue = createSerialSaveQueue({ save })

    queue.enqueue({ visibility: 'public' })
    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(1))
    queue.enqueue({ visibility: 'unlisted', enabled: false })
    expect(save).toHaveBeenCalledTimes(1)

    first.resolve({ visibility: 'public' })
    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(2))
    expect(save).toHaveBeenLastCalledWith({ visibility: 'unlisted', enabled: false })
    second.resolve({ visibility: 'unlisted', enabled: false })
    await queue.waitForIdle()
  })

  it('retains failed changes and retries them with newer values winning', async () => {
    const save = vi.fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ visibility: 'private' })
    const states: string[] = []
    const queue = createSerialSaveQueue({
      save,
      onStateChange: state => states.push(state)
    })

    queue.enqueue({ visibility: 'public', enabled: true })
    await queue.waitForIdle()
    queue.enqueue({ visibility: 'private' })
    queue.retry()
    await queue.waitForIdle()

    expect(save).toHaveBeenCalledTimes(2)
    expect(save).toHaveBeenLastCalledWith({ visibility: 'private', enabled: true })
    expect(states).toContain('error')
    expect(states.at(-1)).toBe('saved')
  })
})
