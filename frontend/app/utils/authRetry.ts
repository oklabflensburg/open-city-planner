export type AuthFailure = {
  status: number
  code?: string
}

let activeRefresh: Promise<boolean> | null = null

export async function singleFlightRefresh(task: () => Promise<boolean>): Promise<boolean> {
  if (!activeRefresh) {
    activeRefresh = task().finally(() => {
      activeRefresh = null
    })
  }
  return await activeRefresh
}

export async function executeWithRefreshRetry<T>(options: {
  send: () => Promise<T>
  failure: (result: T) => Promise<AuthFailure>
  refresh: () => Promise<boolean>
  canRefresh: (failure: AuthFailure) => boolean
}): Promise<T> {
  const first = await options.send()
  const failure = await options.failure(first)
  if (!options.canRefresh(failure)) return first
  if (!await options.refresh()) return first
  return await options.send()
}
