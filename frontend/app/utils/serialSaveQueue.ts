export type SerialSaveState = 'saved' | 'saving' | 'error'

interface SerialSaveQueueOptions<P extends object, R> {
  save: (patch: P) => Promise<R>
  onSaved?: (result: R, patch: P) => void
  onStateChange?: (state: SerialSaveState, error?: unknown) => void
}

export function createSerialSaveQueue<P extends object, R>(options: SerialSaveQueueOptions<P, R>) {
  let pending: Partial<P> = {}
  let active = false
  let blocked = false
  let scheduled = false
  let idleWaiters: Array<() => void> = []

  function hasPending() {
    return Object.keys(pending).length > 0
  }

  function notifyIdle() {
    if (active || scheduled) return
    const waiters = idleWaiters
    idleWaiters = []
    waiters.forEach(resolve => resolve())
  }

  function schedule() {
    if (active || blocked || scheduled || !hasPending()) return
    scheduled = true
    queueMicrotask(() => {
      scheduled = false
      void drain()
    })
  }

  async function drain() {
    if (active || blocked || !hasPending()) {
      notifyIdle()
      return
    }

    const snapshot = { ...pending } as P
    pending = {}
    active = true
    options.onStateChange?.('saving')
    try {
      const result = await options.save(snapshot)
      options.onSaved?.(result, snapshot)
    } catch (error) {
      // Values queued while the request was running are newer and must win.
      pending = { ...snapshot, ...pending }
      blocked = true
      options.onStateChange?.('error', error)
    } finally {
      active = false
    }

    if (!blocked && hasPending()) {
      schedule()
    } else if (!blocked) {
      options.onStateChange?.('saved')
    }
    notifyIdle()
  }

  function enqueue(patch: Partial<P>) {
    pending = { ...pending, ...patch }
    if (!blocked) options.onStateChange?.('saving')
    schedule()
  }

  function retry() {
    if (!hasPending()) return
    blocked = false
    options.onStateChange?.('saving')
    schedule()
  }

  async function waitForIdle() {
    if (!active && !scheduled) return
    await new Promise<void>(resolve => idleWaiters.push(resolve))
  }

  async function flush() {
    schedule()
    await waitForIdle()
  }

  return {
    enqueue,
    retry,
    flush,
    waitForIdle,
    hasPending: () => hasPending() || active || scheduled,
  }
}
