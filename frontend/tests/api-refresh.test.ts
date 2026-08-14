import { describe, expect, it, vi } from 'vitest'
import { executeWithRefreshRetry, singleFlightRefresh } from '../app/utils/authRetry'

type Result = { status: number, code?: string, value?: string }
const failure = async (result: Result) => ({ status: result.status, code: result.code })
const canRefresh = (result: { status: number, code?: string }) => result.status === 401 && result.code === 'ACCESS_TOKEN_EXPIRED'

describe('central API refresh retry', () => {
  it('does not refresh a successful request', async () => {
    const send = vi.fn().mockResolvedValue({ status: 200, value: 'ok' })
    const refresh = vi.fn().mockResolvedValue(true)

    const result = await executeWithRefreshRetry({ send, failure, refresh, canRefresh })

    expect(result.value).toBe('ok')
    expect(send).toHaveBeenCalledOnce()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('refreshes an expired access token and retries exactly once', async () => {
    const send = vi.fn()
      .mockResolvedValueOnce({ status: 401, code: 'ACCESS_TOKEN_EXPIRED' })
      .mockResolvedValueOnce({ status: 200, value: 'retried' })
    const refresh = vi.fn().mockResolvedValue(true)

    const result = await executeWithRefreshRetry({ send, failure, refresh, canRefresh })

    expect(result.value).toBe('retried')
    expect(refresh).toHaveBeenCalledOnce()
    expect(send).toHaveBeenCalledTimes(2)
  })

  it('returns the original auth failure when refresh is rejected', async () => {
    const original = { status: 401, code: 'ACCESS_TOKEN_EXPIRED' }
    const send = vi.fn().mockResolvedValue(original)

    const result = await executeWithRefreshRetry({
      send,
      failure,
      refresh: vi.fn().mockResolvedValue(false),
      canRefresh
    })

    expect(result).toBe(original)
    expect(send).toHaveBeenCalledOnce()
  })

  it('uses one refresh flight for five concurrent 401 responses', async () => {
    let refreshCalls = 0
    const refresh = () => singleFlightRefresh(async () => {
      refreshCalls += 1
      await Promise.resolve()
      return true
    })
    const sends = Array.from({ length: 5 }, () => vi.fn()
      .mockResolvedValueOnce({ status: 401, code: 'ACCESS_TOKEN_EXPIRED' })
      .mockResolvedValueOnce({ status: 200, value: 'ok' }))

    const results = await Promise.all(sends.map(send => executeWithRefreshRetry({ send, failure, refresh, canRefresh })))

    expect(refreshCalls).toBe(1)
    expect(results.every(result => result.status === 200)).toBe(true)
    expect(sends.every(send => send.mock.calls.length === 2)).toBe(true)
  })

  it('never refreshes a 403 response or an excluded request', async () => {
    const refresh = vi.fn().mockResolvedValue(true)
    const forbidden = await executeWithRefreshRetry({
      send: vi.fn().mockResolvedValue({ status: 403, code: 'ROLE_REQUIRED' }),
      failure,
      refresh,
      canRefresh
    })
    const excluded = await executeWithRefreshRetry({
      send: vi.fn().mockResolvedValue({ status: 401, code: 'ACCESS_TOKEN_EXPIRED' }),
      failure,
      refresh,
      canRefresh: () => false
    })

    expect(forbidden.status).toBe(403)
    expect(excluded.status).toBe(401)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('does not hide a temporary refresh network failure', async () => {
    const networkError = new TypeError('network unavailable')
    await expect(executeWithRefreshRetry({
      send: vi.fn().mockResolvedValue({ status: 401, code: 'ACCESS_TOKEN_EXPIRED' }),
      failure,
      refresh: vi.fn().mockRejectedValue(networkError),
      canRefresh
    })).rejects.toBe(networkError)
  })
})
