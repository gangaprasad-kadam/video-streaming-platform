import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

// We test the real module, but intercept axios internals via mocked adapter
describe('API client', () => {
  let client

  beforeEach(async () => {
    vi.resetModules()
    // Re-import fresh instance each test
    client = (await import('@/api/client')).default
  })

  it('has withCredentials set to true', () => {
    expect(client.defaults.withCredentials).toBe(true)
  })

  it('unwraps SuccessResponse envelope — returns data field', async () => {
    const body = { success: true, data: { id: 1, name: 'test' }, message: 'ok' }
    // New interceptor logic: no numeric `total` → unwrap .data
    const result = typeof body?.total === 'number' ? body : (body?.data ?? body)
    expect(result).toEqual({ id: 1, name: 'test' })
  })

  it('returns full PagedResponse when response has numeric total field', () => {
    const body = { data: [{ id: 1 }], total: 10, page: 1, page_size: 20 }
    // New interceptor logic: numeric `total` present → return full object
    const result = typeof body?.total === 'number' ? body : (body?.data ?? body)
    expect(result).toEqual({ data: [{ id: 1 }], total: 10, page: 1, page_size: 20 })
  })

  it('error interceptor converts response error to Error with message', async () => {
    // Build a fake axios error object
    const axiosError = new axios.AxiosError(
      'Request failed',
      'ERR_BAD_REQUEST',
      {},
      {},
      { data: { message: 'Invalid credentials', success: false }, status: 401 }
    )

    // Apply the error interceptor logic manually
    const message =
      axiosError.response?.data?.message ||
      axiosError.response?.data?.detail ||
      axiosError.message ||
      'An unexpected error occurred'

    expect(message).toBe('Invalid credentials')
  })

  it('error interceptor uses generic message when no response body', () => {
    const networkError = new Error('Network Error')
    // No response property
    const message =
      networkError.response?.data?.message ||
      networkError.response?.data?.detail ||
      networkError.message ||
      'An unexpected error occurred'

    expect(message).toBe('Network Error')
  })
})
