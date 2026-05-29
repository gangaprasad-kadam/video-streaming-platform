import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useVideoStatus from '@/hooks/useVideoStatus'

vi.mock('@/api/videos', () => ({
  getVideoStatus: vi.fn(),
}))
import { getVideoStatus } from '@/api/videos'

describe('useVideoStatus', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks() })
  afterEach(()  => { vi.useRealTimers() })

  it('T6.1 — polls every 3s while non-terminal', async () => {
    getVideoStatus.mockResolvedValue({ status: 'processing' })
    renderHook(() => useVideoStatus('v1', 'processing'))
    await act(async () => { vi.advanceTimersByTime(9001) })
    expect(getVideoStatus).toHaveBeenCalledTimes(3)
  })

  it('T6.2 — stops polling when status = ready', async () => {
    getVideoStatus.mockResolvedValue({ status: 'ready' })
    const { result } = renderHook(() => useVideoStatus('v1', 'processing'))
    await act(async () => { vi.advanceTimersByTime(3001) })
    const calls = getVideoStatus.mock.calls.length
    await act(async () => { vi.advanceTimersByTime(9000) })
    expect(getVideoStatus.mock.calls.length).toBe(calls)  // no more calls
    expect(result.current.status).toBe('ready')
  })

  it('T6.3 — stops polling when status = failed', async () => {
    getVideoStatus.mockResolvedValue({ status: 'failed' })
    const { result } = renderHook(() => useVideoStatus('v1', 'processing'))
    await act(async () => { vi.advanceTimersByTime(3001) })
    expect(result.current.status).toBe('failed')
    const calls = getVideoStatus.mock.calls.length
    await act(async () => { vi.advanceTimersByTime(9000) })
    expect(getVideoStatus.mock.calls.length).toBe(calls)
  })

  it('T6.4 — returns current status and null error on success', async () => {
    getVideoStatus.mockResolvedValue({ status: 'processing' })
    const { result } = renderHook(() => useVideoStatus('v1', 'uploading'))
    await act(async () => { vi.advanceTimersByTime(3001) })
    expect(result.current.status).toBe('processing')
    expect(result.current.error).toBeNull()
  })

  it('does not poll when no videoId', async () => {
    renderHook(() => useVideoStatus(null, 'uploading'))
    await act(async () => { vi.advanceTimersByTime(9001) })
    expect(getVideoStatus).not.toHaveBeenCalled()
  })
})
